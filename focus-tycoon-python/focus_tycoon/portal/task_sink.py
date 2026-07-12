"""A place to put scraped tasks, with de-duplicating upsert.

Hybrid rule: this never triggers the AI split or the reward system. Only newly
imported tasks can later be split on demand.

This is a base class; real sinks override upsert().
"""

from __future__ import annotations


class UpsertResult:
    def __init__(self, imported, skipped):
        self.imported = imported  # newly inserted
        self.skipped = skipped    # already present (updated)


class TaskSink:
    def upsert(self, tasks):
        raise NotImplementedError("upsert() must be implemented by a subclass")
