"""A single calendar event read from an ICS file."""

from __future__ import annotations


class CalendarEvent:
    def __init__(self, summary, description, location, start, all_day, uid):
        self.summary = summary
        self.description = description
        self.location = location
        self.start = start
        self.all_day = all_day
        self.uid = uid

    def has_summary(self):
        # Only an event with a meaningful title becomes a quest later.
        return bool(self.summary) and bool(self.summary.strip())

    def __repr__(self):
        return f"CalendarEvent(summary='{self.summary}', start={self.start}, all_day={self.all_day})"
