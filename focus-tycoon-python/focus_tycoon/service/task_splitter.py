"""Breaks big tasks into small steps.

This used to have an offline fallback that made up generic steps. That fallback
is gone: we always ask the real AI. If the AI is not reachable, GeminiService
retries for a minute and then raises a clear error, which the UI shows to the
user. We never silently invent steps any more.
"""

from __future__ import annotations

from .gemini_service import GeminiService, SPLIT_MEDIUM


class TaskSplitter:
    def __init__(self, gemini=None):
        if gemini is None:
            gemini = GeminiService()
        self.gemini = gemini

    def is_configured(self):
        return self.gemini.is_configured()

    def break_down(self, input_text, description="", split_level=SPLIT_MEDIUM,
                   estimated_total_minutes=0):
        """Return a list of Task objects, or raise if the AI is unreachable."""
        return self.gemini.break_down_task(
            input_text, description, split_level, estimated_total_minutes)

    def estimate_minutes(self, input_text, description):
        """Return an estimated total number of minutes, or raise on failure."""
        return self.gemini.estimate_minutes(input_text, description)
