"""A loaded save game as plain data, plus methods to apply it to the live objects.

Task deletion rule: fully completed quests are dropped when saving. Quests that
still have open steps are saved completely, including the "completed" flag of
each step, so that finished-but-not-sorted steps stay finished. When loading,
those steps are marked as done again WITHOUT paying out the gold reward twice.

Each tycoon (city, business, ...) is saved as its own opaque dict; the tycoon
object rebuilds itself from that dict when the Tycoon page is created.
"""

from __future__ import annotations

from ..model.game_state import GameState
from ..model.quest import Quest
from ..model.task import Task


class TaskData:
    def __init__(self, title, energy_level, minutes, completed, detail=""):
        self.title = title
        self.energy_level = energy_level
        self.minutes = minutes
        self.completed = completed
        self.detail = detail


class QuestData:
    def __init__(self, title, energy_level, stages):
        self.title = title
        self.energy_level = energy_level
        self.stages = stages


class SaveGame:
    def __init__(self, gold, quests, tycoons):
        self.gold = max(0, gold)
        self.quests = quests
        # A dict of tycoon name -> its opaque saved data (each tycoon rebuilds
        # itself from its own entry; see tycoon_main.build_panel).
        self.tycoons = tycoons if isinstance(tycoons, dict) else {}

    def apply_quests(self, game: GameState) -> None:
        for quest_data in self.quests:
            stages = []
            for task_data in quest_data.stages:
                task = Task(task_data.title, task_data.energy_level,
                            task_data.minutes, task_data.detail)
                # Set the flag directly instead of calling complete_task(),
                # so the gold reward is not paid out a second time for a
                # step that was already finished before saving.
                if task_data.completed:
                    task.completed = True
                stages.append(task)
            # Only keep quests that still have at least one stage.
            if stages:
                game.add_quest(Quest(quest_data.title, quest_data.energy_level, stages))
