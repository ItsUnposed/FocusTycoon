"""Tycoon data model.

Contains: ResourceType (a registry with tier / glyph / colour), Inventory,
Position, Wallet, generator and sector definitions and their live instances,
recipes, milestones and the TycoonState that ties it all together.

Colours are plain (r, g, b) tuples so pygame can use them directly.
"""

from __future__ import annotations

import math
import threading
import uuid

from .economy import GoldAccount

# ---------------------------------------------------------------- ResourceType

# All resources live in one shared registry so new resources can be added from
# the content file without changing this module.
_resource_registry = {}
_resource_lock = threading.Lock()


class ResourceType:
    def __init__(self, resource_id, display_name, tier, glyph, accent):
        self.id = resource_id
        self.display_name = display_name
        # 0 = raw, 1 = refined, 2 = master-crafted. Higher tier = higher feedback tone.
        self.tier = tier
        self.glyph = glyph
        self.accent = accent

    def __eq__(self, other):
        return isinstance(other, ResourceType) and other.id == self.id

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return self.display_name


def register_resource(resource_id, display_name, tier, glyph, accent):
    """Create a resource type once and reuse it for the same id after that."""
    with _resource_lock:
        existing = _resource_registry.get(resource_id)
        if existing is not None:
            return existing
        resource = ResourceType(resource_id, display_name, tier, glyph, accent)
        _resource_registry[resource_id] = resource
        return resource


def get_resource(resource_id):
    resource = _resource_registry.get(resource_id)
    if resource is None:
        raise ValueError(f"Unknown resource type: {resource_id}")
    return resource


# ---------------------------------------------------------------- Inventory

class Inventory:
    """Holds produced / refined resources. Thread-safe."""

    def __init__(self):
        self._stacks = {}
        self._lock = threading.RLock()

    def amount_of(self, resource):
        with self._lock:
            return self._stacks.get(resource, 0.0)

    def add(self, resource, amount):
        if amount <= 0:
            return
        with self._lock:
            self._stacks[resource] = self._stacks.get(resource, 0.0) + amount

    def has(self, resource, amount):
        return self.amount_of(resource) >= amount

    def has_all(self, required):
        with self._lock:
            for resource, amount in required.items():
                if self._stacks.get(resource, 0.0) < amount:
                    return False
            return True

    def remove_all(self, amounts):
        with self._lock:
            for resource, amount in amounts.items():
                remaining = self._stacks.get(resource, 0.0) - amount
                # Never drop below zero (protects against negative amounts).
                self._stacks[resource] = max(0.0, remaining)

    def try_remove_all(self, amounts):
        """Check and remove in one step, so two threads cannot go negative."""
        with self._lock:
            for resource, amount in amounts.items():
                if self._stacks.get(resource, 0.0) < amount:
                    return False
            for resource, amount in amounts.items():
                self._stacks[resource] = max(0.0, self._stacks.get(resource, 0.0) - amount)
            return True

    def set_amount(self, resource, amount):
        with self._lock:
            if amount <= 0:
                self._stacks.pop(resource, None)
            else:
                self._stacks[resource] = amount

    def max_craftable_units(self, per_unit):
        with self._lock:
            max_units = math.inf
            for resource, amount in per_unit.items():
                if amount <= 0:
                    continue
                max_units = min(max_units, self._stacks.get(resource, 0.0) / amount)
            return max(0.0, max_units)

    def snapshot(self):
        with self._lock:
            return dict(self._stacks)


# ---------------------------------------------------------------- Position

class Position:
    """A grid coordinate for placing sectors and producers."""

    def __init__(self, grid_x, grid_y):
        self.grid_x = grid_x
        self.grid_y = grid_y


# ---------------------------------------------------------------- Wallet

class Wallet(GoldAccount):
    """A standalone gold account. Thread-safe."""

    def __init__(self, starting_balance):
        self._balance = max(0.0, starting_balance)
        self._lock = threading.RLock()

    def balance(self):
        with self._lock:
            return self._balance

    def credit(self, amount):
        if amount <= 0:
            return
        with self._lock:
            self._balance += amount

    def try_spend(self, amount):
        if amount <= 0:
            return True
        with self._lock:
            if self._balance < amount:
                return False
            self._balance -= amount
            return True


# ---------------------------------------------------------------- Definitions

class RecipeDefinition:
    """A recipe that names the output of a refinery.

    In this version refineries no longer consume their inputs, so the recipe is
    kept mainly for the output resource and the display name.
    """

    def __init__(self, recipe_id, display_name, inputs_per_unit, output, output_per_unit):
        self.id = recipe_id
        self.display_name = display_name
        self.inputs_per_unit = inputs_per_unit
        self.output = output
        self.output_per_unit = output_per_unit


class GeneratorDefinition:
    """The fixed config of a producer type (ore vein, mana forge, ...)."""

    def __init__(self, generator_id, display_name, output_resource, recipe,
                 base_output_per_second, fuel_burn_seconds, fuel_cost_gold,
                 passive_output_ratio, max_level, base_upgrade_cost,
                 upgrade_cost_growth, glyph, accent):
        self.id = generator_id
        self.display_name = display_name
        self.output_resource = output_resource
        # If a recipe is set, this producer counts as a refinery (tier 1 / 2).
        self.recipe = recipe
        self.base_output_per_second = base_output_per_second
        self.fuel_burn_seconds = fuel_burn_seconds
        self.fuel_cost_gold = fuel_cost_gold
        self.passive_output_ratio = passive_output_ratio
        self.max_level = max_level
        self.base_upgrade_cost = base_upgrade_cost
        self.upgrade_cost_growth = upgrade_cost_growth
        self.glyph = glyph
        self.accent = accent

    def is_refinery(self):
        return self.recipe is not None


class SectorDefinition:
    """The config of a floating island (sector)."""

    def __init__(self, sector_id, display_name, subtitle, origin, width, height,
                 unlock_cost, accent):
        self.id = sector_id
        self.display_name = display_name
        self.subtitle = subtitle
        self.origin = origin
        self.width = width
        self.height = height
        self.unlock_cost = unlock_cost
        self.accent = accent


class MilestoneDefinition:
    """A one-time progress milestone; condition(state) checks if it is reached."""

    def __init__(self, milestone_id, description, condition):
        self.id = milestone_id
        self.description = description
        self.condition = condition


# ---------------------------------------------------------------- Instances

class GeneratorInstance:
    """A placed, running producer built from a GeneratorDefinition. Thread-safe."""

    def __init__(self, definition, position):
        self.instance_id = str(uuid.uuid4())
        self.definition = definition
        self.position = position
        self._level = 1
        self._fuel = 0.0  # 0.0 = empty tank (idle), 1.0 = just cheered
        self._unpulsed_output = 0.0
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def fuel_fraction(self):
        with self._lock:
            return self._fuel

    def is_fueled(self):
        with self._lock:
            return self._fuel > 1e-6

    def remaining_burn_seconds(self):
        with self._lock:
            return self._fuel * self.definition.fuel_burn_seconds

    def _output_multiplier(self):
        return self._level

    def current_output_per_second(self):
        with self._lock:
            if self._fuel > 1e-6:
                efficiency = 1.0
            else:
                efficiency = self.definition.passive_output_ratio
            return self.definition.base_output_per_second * self._output_multiplier() * efficiency

    def ignite(self):
        with self._lock:
            self._fuel = 1.0

    def drain_fuel(self, elapsed_seconds):
        with self._lock:
            if self._fuel <= 0:
                return
            self._fuel = max(0.0, self._fuel - elapsed_seconds / self.definition.fuel_burn_seconds)

    def can_upgrade(self):
        with self._lock:
            return self._level < self.definition.max_level

    def upgrade_cost_at_current_level(self):
        with self._lock:
            if self._level >= self.definition.max_level:
                return {}
            factor = self.definition.upgrade_cost_growth ** (self._level - 1)
            cost = {}
            for resource, amount in self.definition.base_upgrade_cost.items():
                cost[resource] = math.ceil(amount * factor)
            return cost

    def upgrade(self):
        with self._lock:
            if self._level < self.definition.max_level:
                self._level += 1

    def restore_level(self, saved_level):
        with self._lock:
            self._level = max(1, min(self.definition.max_level, saved_level))

    def restore_fuel(self, saved_fuel_fraction):
        with self._lock:
            self._fuel = max(0.0, min(1.0, saved_fuel_fraction))

    def add_unpulsed_output(self, amount):
        with self._lock:
            self._unpulsed_output += amount

    def drain_pulse_if_ready(self, threshold):
        with self._lock:
            if self._unpulsed_output >= threshold:
                total = self._unpulsed_output
                self._unpulsed_output = 0.0
                return total
            return 0.0


class SectorInstance:
    def __init__(self, definition, unlocked):
        self.definition = definition
        self._generators = []
        self._unlocked = unlocked

    def is_unlocked(self):
        return self._unlocked

    def unlock(self):
        self._unlocked = True

    def generators(self):
        return self._generators

    def add_generator(self, instance):
        self._generators.append(instance)


class TycoonState:
    """The aggregate root: the complete Tycoon state."""

    def __init__(self, gold):
        self._gold = gold
        self._inventory = Inventory()
        self._sectors = {}
        self._reached_milestones = set()

    def gold(self):
        return self._gold

    def inventory(self):
        return self._inventory

    def sectors(self):
        return self._sectors

    def add_sector(self, sector):
        self._sectors[sector.definition.id] = sector

    def reached_milestone_ids(self):
        return set(self._reached_milestones)

    def has_reached(self, milestone_id):
        return milestone_id in self._reached_milestones

    def mark_reached(self, milestone_id):
        self._reached_milestones.add(milestone_id)
