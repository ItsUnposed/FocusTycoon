"""Connects the calendar world to the splitting pipeline.

Loads an .ics file or subscription URL, keeps only the upcoming events, and turns
each event into a text the AI can read (build_ai_context).
"""

from __future__ import annotations

import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from . import ics_parser

DEFAULT_WINDOW_DAYS = 14
MAX_EVENTS = 15

_DATE_FORMAT = "%d.%m.%Y"


def _format_date_and_time(moment):
    return f"{moment.strftime('%d.%m.%Y')} at {moment.strftime('%H:%M')}"


def build_ai_context(event):
    """Turn an event into a description the AI can split into steps."""
    parts = [f'Calendar event: "{event.summary.strip()}".']
    if event.start is not None:
        if event.all_day:
            when = event.start.strftime(_DATE_FORMAT)
        else:
            when = _format_date_and_time(event.start)
        parts.append(f" Due on {when}.")
    if event.location and event.location.strip():
        parts.append(f" Location: {event.location.strip()}.")
    if event.description and event.description.strip():
        details = event.description.strip()
        parts.append(f" Details: {details}")
        if not details.endswith("."):
            parts.append(".")
    parts.append(" Create concrete preparation steps so it is finished in time.")
    return "".join(parts)


class CalendarImportService:
    def load_from_file(self, ics_file):
        content = Path(ics_file).read_text(encoding="utf-8")
        return ics_parser.parse(content)

    def load_from_url(self, url):
        normalized = url.strip()
        if normalized[:9].lower() == "webcal://":
            normalized = "https://" + normalized[9:]
        request = urllib.request.Request(normalized, headers={"Accept": "text/calendar"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
        return ics_parser.parse(body)

    def filter_upcoming(self, events, now=None, window_days=DEFAULT_WINDOW_DAYS):
        if now is None:
            now = datetime.now()
        horizon = now + timedelta(days=window_days)
        upcoming = []
        for event in events:
            if event.start is None:
                continue
            if event.start < now or event.start > horizon:
                continue
            upcoming.append(event)

        def start_time(event):
            return event.start

        upcoming.sort(key=start_time)
        return upcoming[:MAX_EVENTS]
