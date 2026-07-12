"""Portal client for Logineo NRW LMS (= Moodle).

It logs in and calls the Moodle calendar JSON API (more robust than HTML scraping).
Dependency-free: http.client + json.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date

from . import portal_urls
from .http import portal_http
from .http.cookie_jar import CookieJar
from .model.scrape_result import ScrapeResult
from .model.scraped_task import ScrapedTask
from .portal_client import PortalClient
from .portal_exception import PortalAuthException, PortalScrapeException
from .util import date_utils, subject_mapper, text_utils

# Moodle embeds the "sesskey" token (needed to call the AJAX API) either as JSON
# on the page, or as a plain query parameter in a link - _extract_session_key()
# below tries both.
_SESSION_KEY_JSON = re.compile(r'"sesskey":"([^"]+)"')
_SESSION_KEY_FORM = re.compile(r"sesskey=([A-Za-z0-9]+)")


def _as_string(value):
    # The Moodle JSON response is not fully trusted, so only accept an actual string.
    return value if isinstance(value, str) else None


def _as_long(value):
    # The Moodle JSON response can encode a number as an int, a float, or even a
    # numeric string, so normalize all of those to a plain int (and reject
    # True/False, which Python also treats as a number).
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


class LogineoClient(PortalClient):
    def scrape(self, school_url, username, password, debug):
        base = portal_urls.origin_of(school_url)
        client = portal_http.new_client()
        jar = CookieJar()

        # 1. Load the login page -> read the login token.
        login_url = base + "/login/index.php"
        login_page = portal_http.get(client, login_url, jar, base)
        login_page = self._settle(client, jar, base, login_page)
        login_token = text_utils.extract_input_value(login_page.body, "logintoken")
        if login_token is None:
            login_token = ""

        # 2. Send the login.
        form = {
            "anchor": "",
            "logintoken": login_token,
            "username": username,
            "password": password,
        }
        post_response = portal_http.post_form(client, login_url, jar, login_url, form)

        # 3. Follow redirects (<= 8 hops), keep the first 200 response.
        status = post_response.status_code
        if 300 <= status < 400:
            location = post_response.location()
            landing = portal_http.follow_redirects(client, jar, base, location, 8)
            html = landing.body if landing is not None else ""
        else:
            html = post_response.body

        # 4./5. Read the session key from the landed HTML.
        session_key = self._extract_session_key(html)

        # 5. Auth error: the login form is shown again OR there is no session key.
        if 'name="logintoken"' in html or session_key is None:
            raise PortalAuthException("Wrong username or password.")

        # 6. Time window (unix seconds), Europe/Berlin.
        past_days = 120 if debug else 14
        start_of_today = date_utils.start_of_today_epoch_berlin()
        time_sort_from = start_of_today - past_days * 86400
        time_sort_to = int(time.time()) + 365 * 86400

        # 7. Call the Moodle AJAX endpoint. The request body has a fixed, known
        # shape, so it is written out directly instead of building it with a
        # dictionary + json.dumps.
        ajax_url = (base + "/lib/ajax/service.php?sesskey=" + portal_http.url_encode(session_key)
                    + "&info=core_calendar_get_action_events_by_timesort")
        body = ('[{"index":0,"methodname":"core_calendar_get_action_events_by_timesort",'
                '"args":{"limitnum":50,"timesortfrom":' + str(time_sort_from)
                + ',"timesortto":' + str(time_sort_to) + ',"limittononsuspendedevents":true}}]')
        ajax_response = portal_http.post_json(client, ajax_url, jar, body)

        # 8. Parse + 9. map.
        tasks = self._parse_events(ajax_response.body)
        debug_info = {"portal": "logineo", "events": len(tasks)}
        return ScrapeResult(tasks, debug_info)

    # ---------- parsing ----------

    def _parse_events(self, raw_json):
        try:
            root = json.loads(raw_json)
        except ValueError:
            raise PortalScrapeException("The calendar data could not be read (invalid response).")
        if not isinstance(root, list) or not root or not isinstance(root[0], dict):
            raise PortalScrapeException("The calendar data could not be read (unexpected format).")
        first = root[0]

        if first.get("error") is True:
            message = "AJAX error"
            exception = first.get("exception")
            if isinstance(exception, dict) and isinstance(exception.get("message"), str):
                message = exception["message"]
            raise PortalScrapeException(message)

        data = first.get("data")
        events = data.get("events") if isinstance(data, dict) else None
        if not isinstance(events, list):
            raise PortalScrapeException("The calendar data could not be read (no events).")

        tasks = []
        seen = set()
        for item in events:
            if not isinstance(item, dict):
                continue
            time_sort = _as_long(item.get("timesort"))
            activity_name = _as_string(item.get("activityname"))
            name = _as_string(item.get("name"))
            event_id = _as_long(item.get("id"))

            # The event needs a title from at least one of the two possible fields.
            has_activity_name = activity_name is not None and activity_name.strip()
            has_name = name is not None and name.strip()
            title_missing = not has_activity_name and not has_name

            if time_sort is None or event_id is None or title_missing:
                continue  # required fields are missing

            title = text_utils.clean_title(activity_name, name)
            due_date = date.fromisoformat(date_utils.iso_date_berlin(time_sort))
            subject = "Other"
            course = item.get("course")
            if isinstance(course, dict):
                subject = subject_mapper.subject_from_course(
                    _as_string(course.get("shortname")), _as_string(course.get("fullname")))
            external_id = "logineo_" + str(event_id)
            if external_id not in seen:
                seen.add(external_id)
                tasks.append(ScrapedTask(subject, title, due_date, external_id))
        return tasks

    def _extract_session_key(self, html):
        match_a = _SESSION_KEY_JSON.search(html)
        if match_a:
            return match_a.group(1)
        match_b = _SESSION_KEY_FORM.search(html)
        if match_b:
            return match_b.group(1)
        return None

    def _settle(self, client, jar, base, response):
        # Follow redirects of the first GET response until a non-redirect answer.
        if 300 <= response.status_code < 400:
            location = response.location()
            settled = portal_http.follow_redirects(client, jar, base, location, 8)
            if settled is not None:
                return settled
        return response
