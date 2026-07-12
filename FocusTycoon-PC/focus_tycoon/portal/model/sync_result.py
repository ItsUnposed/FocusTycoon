"""The result of a sync run, for the UI."""

from __future__ import annotations


class SyncResult:
    def __init__(self, imported, skipped, portal, message):
        self.imported = imported  # newly imported tasks
        self.skipped = skipped    # already present (updated in place)
        self.portal = portal
        self.message = message
