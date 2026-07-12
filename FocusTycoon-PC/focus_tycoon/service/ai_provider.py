"""The AI providers the app could use for the task breakdown.

Right now only Gemini is wired up; this enum is kept for a possible future choice.
"""

from __future__ import annotations

from enum import Enum


class AiProvider(Enum):
    GEMINI = "Gemini"
    CLAUDE = "Claude"

    def get_display_name(self):
        return self.value
