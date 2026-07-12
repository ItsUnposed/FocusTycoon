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
from ..tycoon.model import TycoonState
from .save_game import GeneratorData, QuestData, SaveGame, TaskData, TycoonData

SAVE_VERSION = 1


def round_to_three_decimals(value):
    return round(value * 1000.0) / 1000.0


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

    def _serialize(self, game: GameState, tycoon: TycoonState):
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

        inventory = {}
        for resource, amount in tycoon.inventory().snapshot().items():
            # Skip resources the player has none of, to keep the save file small.
            if amount > 0:
                inventory[resource.id] = round_to_three_decimals(amount)

        sectors = {}
        for sector in tycoon.sectors().values():
            sectors[sector.definition.id] = sector.is_unlocked()

        generators = {}
        for sector in tycoon.sectors().values():
            for generator in sector.generators():
                generators[generator.definition.id] = {
                    "level": generator.level(),
                    "fuel": round_to_three_decimals(generator.fuel_fraction()),
                }

        root["tycoon"] = {
            "inventory": inventory,
            "sectors": sectors,
            "generators": generators,
            "milestones": list(tycoon.reached_milestone_ids()),
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
            tycoon = self._parse_tycoon(root.get("tycoon"))
            return SaveGame(gold, quests, tycoon)
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
                            self._read_int(stage.get("minutes"), 10),
                            stage.get("completed") is True,
                            detail))
            if stages:
                result.append(QuestData(title, energy_level, stages))
        return result

    def _parse_tycoon(self, raw):
        inventory = {}
        sectors = {}
        generators = {}
        milestones = []
        if isinstance(raw, dict):
            if isinstance(raw.get("inventory"), dict):
                for key, value in raw["inventory"].items():
                    inventory[str(key)] = self._read_float(value, 0.0)
            if isinstance(raw.get("sectors"), dict):
                for key, value in raw["sectors"].items():
                    sectors[str(key)] = value is True
            if isinstance(raw.get("generators"), dict):
                for key, value in raw["generators"].items():
                    if isinstance(value, dict):
                        generators[str(key)] = GeneratorData(
                            self._read_int(value.get("level"), 1),
                            self._read_float(value.get("fuel"), 0.0))
            if isinstance(raw.get("milestones"), list):
                milestones = [str(m) for m in raw["milestones"]]
        return TycoonData(inventory, sectors, generators, milestones)

    def _read_int(self, value, fallback):
        # In Python, True and False also count as int/float values (1 and 0),
        # so they are excluded here to avoid treating a stray "true"/"false"
        # in the save file as a number.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        return fallback

    def _read_float(self, value, fallback):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return fallback
