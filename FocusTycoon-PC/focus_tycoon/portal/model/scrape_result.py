"""The result of a scrape."""

from __future__ import annotations


class ScrapeResult:
    def __init__(self, tasks, debug):
        self.tasks = tasks
        self.debug = debug
