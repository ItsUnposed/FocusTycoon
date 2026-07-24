"""A loaded save game as plain data, plus methods to apply it to the live objects.

Task deletion rule: fully completed quests are dropped when saving. Quests that
still have open steps are saved completely, including the "completed" flag of
each step, so that finished-but-not-sorted steps stay finished. When loading,
those steps are marked as done again WITHOUT paying out the gold reward twice.

The city is saved as a flat list of buildings (type, tile, level) plus the
milestones already reached.
"""

from __future__ import annotations

from ..model.game_state import GameState
from ..model.quest import Quest
from ..model.task import Task
from ..tycoon.city_model import BuildingInstance


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


class CityBuildingData:
    def __init__(self, building_id, grid_x, grid_y, level):
        self.building_id = building_id
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.level = level


class CityData:
    def __init__(self, buildings, coins, milestones):
        self.buildings = buildings
        self.coins = coins
        self.milestones = milestones


class SaveGame:
    def __init__(self, gold, quests, city):
        self.gold = max(0, gold)
        self.quests = quests
        self.city = city

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

    def apply_city(self, state, catalog) -> None:
        """Rebuild the saved city onto a fresh CityState.

        `catalog` is the list of building definitions, used to turn a saved
        building id back into a real definition. Buildings with an unknown id or
        an invalid / occupied tile are skipped, so an edited or outdated save can
        never crash the app.
        """
        if self.city is None:
            return
        state.set_coins(self.city.coins)
        definitions_by_id = {definition.id: definition for definition in catalog}
        for building_data in self.city.buildings:
            definition = definitions_by_id.get(building_data.building_id)
            if definition is None:
                continue
            if not state.in_bounds(building_data.grid_x, building_data.grid_y):
                continue
            if not state.is_empty(building_data.grid_x, building_data.grid_y):
                continue
            instance = BuildingInstance(definition, building_data.grid_x, building_data.grid_y)
            instance.restore_level(building_data.level)
            state.place(instance)
        for milestone_id in self.city.milestones:
            state.mark_reached(milestone_id)
