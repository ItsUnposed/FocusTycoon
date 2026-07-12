"""Connects the abstract TaskSink to the game's GameState.

Scraped tasks are inserted as raw ImportedHomework (de-duplicated by external id;
splitting happens later, on demand).
"""

from __future__ import annotations

from ..model.game_state import GameState
from ..model.imported_homework import ImportedHomework
from .task_sink import TaskSink, UpsertResult


class GameStateTaskSink(TaskSink):
    def __init__(self, game: GameState):
        self._game = game

    def upsert(self, tasks):
        imported = 0
        skipped = 0
        for task in tasks:
            is_new = self._game.upsert_imported_homework(ImportedHomework(
                task.subject, task.title, task.due_date, task.external_portal_id, False))
            if is_new:
                imported += 1
            else:
                skipped += 1
        return UpsertResult(imported, skipped)
