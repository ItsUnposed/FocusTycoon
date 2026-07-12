"""A homework item imported from a school portal."""

from __future__ import annotations


class ImportedHomework:
    def __init__(self, subject, title, due_date, external_portal_id, decomposed):
        self.subject = subject
        self.title = title
        self.due_date = due_date
        self.external_portal_id = external_portal_id
        # True once the item has been split into a quest (never reset back).
        self.decomposed = decomposed

    def as_decomposed(self):
        return ImportedHomework(self.subject, self.title, self.due_date, self.external_portal_id, True)
