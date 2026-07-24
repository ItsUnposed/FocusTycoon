"""Saves and loads the game to ~/.focustycoon/save.json.

We save the gold, only the OPEN tasks, and the whole Tycoon progress. Completed
tasks are gone after a restart (that is on purpose). Every error is caught so a
broken or old save file can never crash the app.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ..model.game_state import GameState
from ..tycoon.city_model import CityState
from .save_game import CityBuildingData, CityData, QuestData, SaveGame, TaskData

SAVE_VERSION = 2


class SaveManager:
    def __init__(self, save_file=None):
        if save_file is None:
            save_file = Path.home() / ".focustycoon" / "save.json"
        self.save_file = save_file
        self._lock = threading.RLock()

    def save_exists(self):
        return self.save_file.is_file()

    def delete(self):
        with self._lock:
            try:
                self.save_file.unlink(missing_ok=True)
                # save() below writes to a ".tmp" file first. If the app was
                # closed mid-save, that leftover file needs cleaning up too.
                temporary_file = self.save_file.with_name(self.save_file.name + ".tmp")
                temporary_file.unlink(missing_ok=True)
            except Exception as error:
                print(f"Could not delete the save game: {error}")

    # ---------- saving ----------

    def save(self, game: GameState, tycoon: TycoonState):
        with self._lock:
            try:
                self.save_file.parent.mkdir(parents=True, exist_ok=True)
                text = json.dumps(self._serialize(game, tycoon), ensure_ascii=False, indent=2)
                # Write to a temporary file first, then rename it into place.
                # If the app crashes mid-write, the real save file is never
                # left half-written.
                temporary_file = self.save_file.with_name(self.save_file.name + ".tmp")
                temporary_file.write_text(text, encoding="utf-8")
                temporary_file.replace(self.save_file)  # atomic rename
            except Exception as error:
                print(f"Could not save the game: {error}")

    def _serialize(self, game: GameState, city: CityState):
        root = {"version": SAVE_VERSION, "gold": max(0, game.get_gold())}

        # Deletion rule: drop fully completed quests; keep partly-done quests
        # completely (including each step's completed flag).
        quests = []
        for quest in game.get_quests():
            if quest.is_completed():
                continue
            stages = quest.get_stages()
            if not stages:
                continue
            saved_stages = []
            for stage in stages:
                saved_stages.append({
                    "title": stage.title,
                    "detail": stage.detail,
                    "energyLevel": stage.energy_level,
                    "minutes": stage.estimated_minutes,
                    "completed": stage.completed,
                })
            quests.append({
                "title": quest.title,
                "energyLevel": quest.energy_level,
                "stages": saved_stages,
            })
        root["quests"] = quests

        # The city: every placed building (type, tile and level) plus the
        # milestones that have already been celebrated.
        buildings = []
        for building in city.buildings():
            buildings.append({
                "id": building.definition.id,
                "x": building.grid_x,
                "y": building.grid_y,
                "level": building.level(),
            })
        root["city"] = {
            "buildings": buildings,
            "coins": round(city.coins(), 2),
            "milestones": list(city.reached_milestone_ids()),
        }
        return root

    # ---------- loading ----------

    def load(self):
        if not self.save_file.is_file():
            return None
        try:
            root = json.loads(self.save_file.read_text(encoding="utf-8"))
            gold = self._read_int(root.get("gold"), 0)
            quests = self._parse_quests(root.get("quests"))
            city = self._parse_city(root.get("city"))
            return SaveGame(gold, quests, city)
        except Exception as error:
            print(f"Could not load the save game (ignored): {error}")
            return None

    def _parse_quests(self, raw):
        # The save file might be from an older version or slightly damaged,
        # so every field is read defensively with a safe fallback value
        # instead of trusting it and possibly crashing the app.
        result = []
        if not isinstance(raw, list):
            return result
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "Task"))
            energy_level = self._read_int(item.get("energyLevel"), 2)
            stages = []
            raw_stages = item.get("stages")
            if isinstance(raw_stages, list):
                for stage in raw_stages:
                    if isinstance(stage, dict):
                        # Older save files might not have a "detail" field at
                        # all, so fall back to an empty string instead of the
                        # text "None".
                        detail_value = stage.get("detail")
                        if detail_value is None:
                            detail = ""
                        else:
                            detail = str(detail_value)
                        stages.append(TaskData(
                            str(stage.get("title", "Step")),
                            self._read_int(stage.get("energyLevel"), energy_level),
                            self._read_optional_minutes(stage),
                            stage.get("completed") is True,
                            detail))
            if stages:
                result.append(QuestData(title, energy_level, stages))
        return result

    def _parse_city(self, raw):
        # Read the city defensively: an old or damaged save should never crash
        # the app, so unknown or missing fields just fall back to safe values.
        buildings = []
        milestones = []
        coins = 0.0
        if isinstance(raw, dict):
            if isinstance(raw.get("buildings"), list):
                for item in raw["buildings"]:
                    if isinstance(item, dict):
                        building_id = str(item.get("id", ""))
                        if not building_id:
                            continue
                        buildings.append(CityBuildingData(
                            building_id,
                            self._read_int(item.get("x"), -1),
                            self._read_int(item.get("y"), -1),
                            self._read_int(item.get("level"), 1)))
            if isinstance(raw.get("coins"), (int, float)) and not isinstance(raw.get("coins"), bool):
                coins = float(raw["coins"])
            if isinstance(raw.get("milestones"), list):
                milestones = [str(m) for m in raw["milestones"]]
        return CityData(buildings, coins, milestones)

    def _read_optional_minutes(self, stage):
        # A step's estimated time is optional: it may be a number, or it may be
        # explicitly "no estimated time" (saved as null / None).
        #   - key missing entirely: a very old save that always had a time, so
        #     fall back to the old default of 10 minutes.
        #   - value is null: the step deliberately has no estimated time -> None.
        #   - value is a number: use that number.
        if "minutes" not in stage:
            return 10
        value = stage.get("minutes")
        if value is None:
            return None
        return self._read_int(value, 10)

    def _read_int(self, value, fallback):
        # In Python, True and False also count as int/float values (1 and 0),
        # so they are excluded here to avoid treating a stray "true"/"false"
        # in the save file as a number.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        return fallback
