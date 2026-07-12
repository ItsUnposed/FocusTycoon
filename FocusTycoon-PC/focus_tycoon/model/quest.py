"""A big task that has been split into ordered stages (micro-tasks).

The player decides the order of the stages, so they can be moved up and down.
"""

from __future__ import annotations

import itertools
import threading

from .task import Task

# Every quest gets a unique id. A lock keeps this safe if two threads create
# quests at the same time.
_id_lock = threading.Lock()
_id_counter = itertools.count(1)


def create_next_quest_id() -> int:
    with _id_lock:
        return next(_id_counter)


class Quest:
    def __init__(self, title: str, energy_level: int, stages) -> None:
        self.id = create_next_quest_id()
        self.title = title
        self.energy_level = energy_level
        # We keep the real list private and hand out copies, so callers cannot
        # change our list by accident.
        self._stages = list(stages)

    def get_stages(self):
        return list(self._stages)

    def get_stage_count(self) -> int:
        return len(self._stages)

    def get_completed_count(self) -> int:
        completed = 0
        for stage in self._stages:
            if stage.completed:
                completed += 1
        return completed

    def is_completed(self) -> bool:
        if not self._stages:
            return False
        for stage in self._stages:
            if not stage.completed:
                return False
        return True

    def find_next_open_stage(self):
        """The first stage that is not done yet - the one that is 'up next'."""
        for stage in self._stages:
            if not stage.completed:
                return stage
        return None

    def contains(self, task_id: int) -> bool:
        return self._index_of(task_id) >= 0

    def move_stage_up(self, task_id: int) -> bool:
        index = self._index_of(task_id)
        if index > 0:
            # Swap this stage with the one directly above it, using a
            # temporary variable so neither value is lost during the swap.
            stage_to_move = self._stages[index]
            self._stages[index] = self._stages[index - 1]
            self._stages[index - 1] = stage_to_move
            return True
        return False

    def move_stage_down(self, task_id: int) -> bool:
        index = self._index_of(task_id)
        if 0 <= index < len(self._stages) - 1:
            # Swap this stage with the one directly below it.
            stage_to_move = self._stages[index]
            self._stages[index] = self._stages[index + 1]
            self._stages[index + 1] = stage_to_move
            return True
        return False

    def _index_of(self, task_id: int) -> int:
        for index, stage in enumerate(self._stages):
            if stage.id == task_id:
                return index
        return -1
