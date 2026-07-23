"""City-builder data model.

The Tycoon page is a little city you grow by finishing real tasks. Finishing a
task is the only big source of gold; you spend that gold to build and upgrade
buildings on a grid. Houses add residents (population), shops and offices add a
small passive gold income, and reaching population goals unlocks fancier
buildings.

Everything here is plain data plus a CityState that ties it together. It stays
safe to touch from both the simulation thread (passive income) and the UI thread
(building and upgrading), so the shared parts are guarded by locks.
"""

from __future__ import annotations

import math
import threading
import uuid

# Building categories. Kept as plain strings so the content file reads clearly.
RESIDENTIAL = "residential"   # adds residents (population)
COMMERCIAL = "commercial"     # adds passive gold income
CIVIC = "civic"               # parks and landmarks: a bit of both / for looks


class BuildingDefinition:
    """The fixed config of one kind of building (a house, a shop, ...)."""

    def __init__(self, building_id, display_name, category, build_cost_gold,
                 base_population, base_income_per_second, max_level,
                 base_upgrade_cost_gold, upgrade_cost_growth, unlock_population,
                 floors, wall_color, roof_color):
        self.id = building_id
        self.display_name = display_name
        self.category = category
        # Gold paid once to place the building on an empty tile.
        self.build_cost_gold = build_cost_gold
        # Residents and gold-per-second this building gives at level 1.
        self.base_population = base_population
        self.base_income_per_second = base_income_per_second
        self.max_level = max_level
        # Upgrading costs gold; each level makes the next one cost more.
        self.base_upgrade_cost_gold = base_upgrade_cost_gold
        self.upgrade_cost_growth = upgrade_cost_growth
        # The city's total population must reach this before the building can be
        # built at all (0 means it is available from the very start).
        self.unlock_population = unlock_population
        # How many floors tall to draw it - this is what makes the skyline grow.
        self.floors = floors
        self.wall_color = wall_color
        self.roof_color = roof_color


class BuildingInstance:
    """One placed building on the city grid. Thread-safe."""

    def __init__(self, definition, grid_x, grid_y):
        self.instance_id = str(uuid.uuid4())
        self.definition = definition
        self.grid_x = grid_x
        self.grid_y = grid_y
        self._level = 1
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def population(self):
        # Residents scale straight with the level.
        with self._lock:
            return self.definition.base_population * self._level

    def income_per_second(self):
        with self._lock:
            return self.definition.base_income_per_second * self._level

    def can_upgrade(self):
        with self._lock:
            return self._level < self.definition.max_level

    def upgrade_cost(self):
        """Gold to raise this building by one level, or 0 if it is maxed."""
        with self._lock:
            if self._level >= self.definition.max_level:
                return 0
            factor = self.definition.upgrade_cost_growth ** (self._level - 1)
            return math.ceil(self.definition.base_upgrade_cost_gold * factor)

    def upgrade(self):
        with self._lock:
            if self._level < self.definition.max_level:
                self._level += 1

    def restore_level(self, saved_level):
        with self._lock:
            # Clamp in case an old save has a level beyond the current maximum.
            self._level = max(1, min(self.definition.max_level, saved_level))


class CityState:
    """The whole city: the gold account, the grid of buildings and progress."""

    def __init__(self, gold, columns, rows):
        self._gold = gold
        self.columns = columns
        self.rows = rows
        # Buildings are stored by their (x, y) tile, so at most one per tile.
        self._buildings = {}
        self._reached_milestones = set()
        self._lock = threading.RLock()

    def gold(self):
        return self._gold

    # ---------- the grid ----------

    def in_bounds(self, x, y):
        return 0 <= x < self.columns and 0 <= y < self.rows

    def building_at(self, x, y):
        with self._lock:
            return self._buildings.get((x, y))

    def is_empty(self, x, y):
        with self._lock:
            return (x, y) not in self._buildings

    def buildings(self):
        with self._lock:
            return list(self._buildings.values())

    def building_count(self):
        with self._lock:
            return len(self._buildings)

    def place(self, instance):
        with self._lock:
            self._buildings[(instance.grid_x, instance.grid_y)] = instance

    # ---------- totals ----------

    def total_population(self):
        with self._lock:
            total = 0
            for building in self._buildings.values():
                total += building.population()
            return total

    def total_income_per_second(self):
        with self._lock:
            total = 0.0
            for building in self._buildings.values():
                total += building.income_per_second()
            return total

    # ---------- milestones ----------

    def reached_milestone_ids(self):
        with self._lock:
            return set(self._reached_milestones)

    def has_reached(self, milestone_id):
        with self._lock:
            return milestone_id in self._reached_milestones

    def mark_reached(self, milestone_id):
        with self._lock:
            self._reached_milestones.add(milestone_id)
