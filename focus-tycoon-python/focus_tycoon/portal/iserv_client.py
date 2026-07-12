"""Portal client for IServ.

It logs in through a form behind an OIDC / meta-refresh handshake, then scrapes
the HTML of /iserv/exercise with three fallback strategies (table rows -> exercise
links -> inline JSON). Dependency-free.
"""

from __future__ import annotations

import json
import re
from datetime import date

from . import portal_urls
from .http import http_navigator, portal_http
from .http.cookie_jar import CookieJar
from .model.scrape_result import ScrapeResult
from .model.scraped_task import ScrapedTask
from .portal_client import PortalClient
from .portal_exception import PortalAuthException
from .util import date_utils, subject_mapper, text_utils

_TABLE_BODY = re.compile(r"<tbody[^>]*>(.*?)</tbody>", re.IGNORECASE | re.DOTALL)
_TABLE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_EXERCISE_ANCHOR = re.compile(
    r'<a[^>]*href="[^"]*/iserv/exercise/(?:show/)?(\d+)[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL)
_EXERCISE_LINK_GLOBAL = re.compile(
    r'href="/iserv/exercise/show/(\d+)"[^>]*>([^<]+)', re.IGNORECASE | re.DOTALL)
_DATA_ID = re.compile(r'data-(?:exercise-)?id="(\d+)"', re.IGNORECASE)
_INLINE_JSON = re.compile(
    r"(?:window\.exerciseData|exercises)\s*[:=]\s*(\[\{.*?\}\])", re.IGNORECASE | re.DOTALL)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CONTEXT_RADIUS = 600


def _id_string(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_string(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


class IServClient(PortalClient):
    def scrape(self, school_url, username, password, debug):
        # Use only the origin - the user may paste the full OIDC login URL.
        base = portal_urls.origin_of(school_url)
        client = portal_http.new_client()
        jar = CookieJar()
        login_url = base + "/iserv/auth/login"

        # 1. Load the login page, collect the hidden fields (CSRF / target).
        login_page = portal_http.get(client, login_url, jar, base)
        form = dict(text_utils.extract_hidden_inputs(login_page.body))

        # 2. Send the login.
        form["_username"] = username
        form["_password"] = password
        post = portal_http.post_form(client, login_url, jar, login_url, form)
        post_status = post.status_code
        location = post.location()

        # 3. Auth error signals.
        if post_status in (401, 403) or http_navigator.is_login_bounce(location):
            raise PortalAuthException("Wrong username or password.")

        # 4. Let the identity provider session settle (if there is a redirect).
        if location is not None:
            settle = http_navigator.navigate(client, jar, base, location)
            if settle.auth_failed:
                raise PortalAuthException("Wrong username or password.")

        # 5. Real proof of a session: reach /iserv/exercise (incl. meta-refresh hop).
        exercise_result = http_navigator.navigate(client, jar, base, base + "/iserv/exercise")
        if exercise_result.auth_failed or exercise_result.status != 200 or exercise_result.html is None:
            raise PortalAuthException("Login was not accepted. Please check your credentials.")
        html = exercise_result.html
        if 'name="_username"' in html and 'name="_password"' in html:
            raise PortalAuthException("Login was not accepted. Please check your credentials.")

        # 6. Parse (three strategies, the first with hits wins).
        tasks = self._parse_exercises(html)
        debug_info = {"portal": "iserv", "exercises": len(tasks)}
        return ScrapeResult(tasks, debug_info)

    # ---------- parsing ----------

    def _parse_exercises(self, html):
        if "table-empty" in html:
            return []  # a valid empty state - no current exercises
        strategy1 = self._strategy_table_rows(html)
        if strategy1:
            return strategy1
        strategy2 = self._strategy_links(html)
        if strategy2:
            return strategy2
        return self._strategy_inline_json(html)

    def _strategy_table_rows(self, html):
        # Strategy 1: the last <tbody>, one exercise per <tr>.
        table_body = self._last_table_body(html)
        if table_body is None:
            return []
        result = []
        seen = set()
        for row_match in _TABLE_ROW.finditer(table_body):
            row = row_match.group(1)
            exercise_id = None
            title = None
            link = _EXERCISE_ANCHOR.search(row)
            if link:
                exercise_id = link.group(1)
                title = text_utils.strip_tags(link.group(2))
            if exercise_id is None:
                data_id = _DATA_ID.search(row)
                if data_id:
                    exercise_id = data_id.group(1)
            iso_date = date_utils.parse_german_date(row)
            if exercise_id is None or title is None or not title.strip() or not iso_date:
                continue
            external_id = "iserv_" + exercise_id
            if external_id not in seen:
                seen.add(external_id)
                result.append(ScrapedTask(self._subject_of(row), title.strip(),
                                          date.fromisoformat(iso_date), external_id))
        return result

    def _strategy_links(self, html):
        # Strategy 2: global exercise links, date / subject from the context (+/- 600 chars).
        result = []
        seen = set()
        for match in _EXERCISE_LINK_GLOBAL.finditer(html):
            exercise_id = match.group(1)
            title = text_utils.strip_tags(match.group(2))
            external_id = "iserv_" + exercise_id
            if not title.strip() or external_id in seen:
                continue
            low = max(0, match.start() - _CONTEXT_RADIUS)
            high = min(len(html), match.end() + _CONTEXT_RADIUS)
            context = html[low:high]
            iso_date = date_utils.parse_german_date(context)
            if not iso_date:
                continue  # no due date -> not an exercise
            seen.add(external_id)
            result.append(ScrapedTask(self._subject_of(context), title.strip(),
                                      date.fromisoformat(iso_date), external_id))
        return result

    def _strategy_inline_json(self, html):
        # Strategy 3: an embedded JSON array of exercises.
        match = _INLINE_JSON.search(html)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(1))
        except ValueError:
            return []
        if not isinstance(parsed, list):
            return []
        result = []
        seen = set()
        for item in parsed:
            if not isinstance(item, dict):
                continue
            exercise_id = _id_string(item.get("id"))
            title = _first_string(item, "title", "name")
            iso_date = self._to_iso(_first_string(item, "dueDate", "deadline", "due"))
            if exercise_id is None or title is None or not title.strip() or not iso_date:
                continue
            raw_subject = _first_string(item, "subject", "course")
            if raw_subject is None or not raw_subject.strip():
                subject = "Other"
            else:
                subject = subject_mapper.normalize_subject(raw_subject)
            external_id = "iserv_" + exercise_id
            if external_id not in seen:
                seen.add(external_id)
                result.append(ScrapedTask(subject, title.strip(), date.fromisoformat(iso_date), external_id))
        return result

    # ---------- helpers ----------

    def _subject_of(self, context):
        raw = text_utils.extract_subject_from_context(context)
        if not raw:
            return "Other"
        return subject_mapper.normalize_subject(raw)

    def _last_table_body(self, html):
        last = None
        for match in _TABLE_BODY.finditer(html):
            last = match.group(1)
        return last

    def _to_iso(self, raw):
        # A German date via parse_german_date; falls back to an existing ISO date.
        if raw is None:
            return ""
        german = date_utils.parse_german_date(raw)
        if german:
            return german
        trimmed = raw.strip()
        return trimmed if _ISO_DATE.match(trimmed) else ""
