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

    def consume_for_output(self, inputs_per_unit, desired_units):
        """Consume inputs for up to `desired_units` of output, all in one locked
        step, and return how many units could actually be made.

        A refinery asks for `desired_units`, but we only let it make as many as
        the scarcest input allows. If an input has run out the refinery simply
        makes less (or nothing) - there is no penalty, it just idles. Doing the
        check and the removal together under the lock keeps the amounts correct
        even when several refineries draw from the same input at once.
        """
        with self._lock:
            units = desired_units
            for resource, amount_per_unit in inputs_per_unit.items():
                if amount_per_unit > 0:
                    available = self._stacks.get(resource, 0.0)
                    # This input can only support this many output units.
                    units = min(units, available / amount_per_unit)
            if units <= 0:
                return 0.0
            for resource, amount_per_unit in inputs_per_unit.items():
                if amount_per_unit > 0:
                    used = amount_per_unit * units
                    self._stacks[resource] = max(0.0, self._stacks.get(resource, 0.0) - used)
            return units

    def max_craftable_units(self, per_unit):
        with self._lock:
            max_units = math.inf
            for resource, amount in per_unit.items():
                if amount <= 0:
                    continue
                # The scarcest required resource is what limits how many units
                # we can make, so we keep shrinking max_units to the smallest
                # available-amount / required-amount ratio seen so far.
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
    """A recipe for a refinery: which inputs it eats and what it makes.

    A refinery consumes `inputs_per_unit` of each input to make `output_per_unit`
    of `output` per unit of work. This is the real crafting chain: raw resources
    are refined into tier-1 goods, which are refined again into tier-2 masters.
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
                 base_output_per_second, max_level, base_upgrade_cost_gold,
                 upgrade_cost_growth, glyph, accent):
        self.id = generator_id
        self.display_name = display_name
        self.output_resource = output_resource
        # If a recipe is set, this producer counts as a refinery (tier 1 / 2).
        self.recipe = recipe
        self.base_output_per_second = base_output_per_second
        self.max_level = max_level
        # Upgrading a producer costs GOLD (the currency you earn from tasks), and
        # each level makes the next one cost more (see the growth factor below).
        self.base_upgrade_cost_gold = base_upgrade_cost_gold
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
        self._unpulsed_output = 0.0
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def current_output_per_second(self):
        with self._lock:
            # Output scales straight with the level. The global Focus Surge
            # multiplies this further, but that happens in the simulation so all
            # producers share the same surge factor.
            return self.definition.base_output_per_second * self._level

    def can_upgrade(self):
        with self._lock:
            return self._level < self.definition.max_level

    def upgrade_cost_at_current_level(self):
        """The gold cost to raise this producer by one level, or 0 if maxed."""
        with self._lock:
            if self._level >= self.definition.max_level:
                return 0
            # Each level makes the next upgrade cost more: the base cost is
            # multiplied by the growth factor raised to the number of levels
            # already gained, so the cost curve grows exponentially.
            factor = self.definition.upgrade_cost_growth ** (self._level - 1)
            return math.ceil(self.definition.base_upgrade_cost_gold * factor)

    def upgrade(self):
        with self._lock:
            if self._level < self.definition.max_level:
                self._level += 1

    def restore_level(self, saved_level):
        with self._lock:
            # Clamp to a valid range in case the save file is old and its
            # level no longer fits within the current max_level.
            self._level = max(1, min(self.definition.max_level, saved_level))

    def add_unpulsed_output(self, amount):
        with self._lock:
            self._unpulsed_output += amount

    def drain_pulse_if_ready(self, threshold):
        with self._lock:
            # Only report output once it has piled up past the threshold, so
            # the juice bus does not fire an event on every single tick.
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
        # Focus Surge: finishing a real task speeds up ALL production for a
        # while. This is the number of seconds the surge still has left. It is
        # transient (never saved) and drains a little on every simulation tick.
        # A lock keeps it safe because the simulation thread drains it while the
        # UI thread tops it up when a task is completed.
        self._surge_seconds = 0.0
        self._surge_lock = threading.Lock()

    def gold(self):
        return self._gold

    # ---------- Focus Surge ----------

    def trigger_surge(self, seconds, cap_seconds):
        """Top up the surge timer by `seconds`, but never above `cap_seconds`."""
        if seconds <= 0:
            return
        with self._surge_lock:
            self._surge_seconds = min(cap_seconds, self._surge_seconds + seconds)

    def drain_surge(self, elapsed_seconds):
        """Let the surge run down by the time that passed this tick."""
        with self._surge_lock:
            if self._surge_seconds <= 0:
                return
            self._surge_seconds = max(0.0, self._surge_seconds - elapsed_seconds)

    def surge_seconds_remaining(self):
        with self._surge_lock:
            return self._surge_seconds

    def is_surging(self):
        return self.surge_seconds_remaining() > 0

    def surge_multiplier(self, active_multiplier):
        """The production multiplier right now: `active_multiplier` while a surge
        is running, otherwise 1.0 (normal slow trickle)."""
        if self.is_surging():
            return active_multiplier
        return 1.0

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
