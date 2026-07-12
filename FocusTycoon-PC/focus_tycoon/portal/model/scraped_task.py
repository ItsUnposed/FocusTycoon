"""A homework item read from a portal - raw, not split yet."""

from __future__ import annotations


class ScrapedTask:
    def __init__(self, subject, title, due_date, external_portal_id):
        self.subject = subject
        self.title = title
        self.due_date = due_date
        # Stable de-duplication id, e.g. "logineo_456" / "iserv_123".
        self.external_portal_id = external_portal_id
