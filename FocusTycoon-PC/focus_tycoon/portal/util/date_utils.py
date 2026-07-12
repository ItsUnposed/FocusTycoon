"""Date helpers for the portal time zone.

Portals give times in Europe/Berlin - never use the system time zone, or a
deadline near midnight can jump to the wrong day.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

try:
    from zoneinfo import ZoneInfo
    _BERLIN = ZoneInfo("Europe/Berlin")
except Exception:  # pragma: no cover - if time zone data is missing
    _BERLIN = timezone.utc

_GERMAN_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")


def iso_date_berlin(unix_seconds):
    """Unix seconds -> 'YYYY-MM-DD' in Europe/Berlin."""
    moment = datetime.fromtimestamp(unix_seconds, tz=_BERLIN)
    return moment.date().isoformat()


def today_berlin():
    """Today's date in Europe/Berlin."""
    return datetime.now(_BERLIN).date()


def start_of_today_epoch_berlin():
    """Unix seconds for today at 00:00 in Europe/Berlin."""
    today = today_berlin()
    midnight = datetime(today.year, today.month, today.day, tzinfo=_BERLIN)
    return int(midnight.timestamp())


def parse_german_date(raw):
    """A German date (dd.mm.yyyy) -> 'YYYY-MM-DD', or '' if it is invalid."""
    if raw is None:
        return ""
    match = _GERMAN_DATE.search(raw)
    if not match:
        return ""
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    if len(match.group(3)) == 2:
        year += 2000
    if day < 1 or day > 31 or month < 1 or month > 12 or year < 2000 or year > 2100:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"
