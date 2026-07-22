"""A loaded save game as plain data, plus methods to apply it to the live objects.

Task deletion rule: fully completed quests are dropped when saving. Quests that
still have open steps are saved completely, including the "completed" flag of
each step, so that finished-but-not-sorted steps stay finished. When loading,
those steps are marked as done again WITHOUT paying out the gold reward twice.
"""

from __future__ import annotations

from ..model.game_state import GameState
from ..model.quest import Quest
from ..model.task import Task
from ..tycoon import model as tycoon_model
from ..tycoon.model import TycoonState


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


class GeneratorData:
    def __init__(self, level):
        self.level = level


class TycoonData:
    def __init__(self, inventory, sectors, generators, milestones):
        self.inventory = inventory
        self.sectors = sectors
        self.generators = generators
        self.milestones = milestones


class SaveGame:
    def __init__(self, gold, quests, tycoon):
        self.gold = max(0, gold)
        self.quests = quests
        self.tycoon = tycoon

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

    def apply_tycoon(self, state: TycoonState) -> None:
        if self.tycoon is None:
            return

        # Inventory
        for resource_id, amount in self.tycoon.inventory.items():
            try:
                state.inventory().set_amount(tycoon_model.get_resource(resource_id), amount)
            except Exception:
                # Unknown resource id (old save format) - just skip it.
                pass

        # Sectors (only unlock; sectors that start locked stay locked otherwise)
        for sector in state.sectors().values():
            if self.tycoon.sectors.get(sector.definition.id) is True:
                sector.unlock()

        # Producers (each definition id appears exactly once in the world)
        for sector in state.sectors().values():
            for generator in sector.generators():
                generator_data = self.tycoon.generators.get(generator.definition.id)
                if generator_data is not None:
                    generator.restore_level(generator_data.level)

        # Milestones (so the celebration effects do not fire again)
        for milestone_id in self.tycoon.milestones:
            state.mark_reached(milestone_id)
