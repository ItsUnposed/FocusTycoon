"""City simulation: passive income, milestones and the player build actions.

The simulation runs on a background thread (see core.GameLoop): every tick it
adds a little gold from the city's income buildings and checks whether any
population milestone has just been reached. Building and upgrading happen on the
UI thread through CityActions.

City events (BuildingPlaced, BuildingUpgraded, BuildingSold, CityMilestoneReached)
are sent on the shared juice bus so the view can pop up a "+1", play a sound, etc.
"""

from __future__ import annotations

from .city_model import BuildingInstance
from .juice import JuiceEventBus


class CityBalance:
    """Central tuning numbers for the city."""

    # Simulation ticks per second (rendering runs on its own timer).
    TICK_RATE_HZ = 8
    # Gold a fresh player starts with when the city runs on its own (no tasks).
    STANDALONE_STARTING_GOLD = 300.0
    # Selling a building refunds this share of its build cost (in gold).
    SELL_REFUND_FRACTION = 0.75


# ---------------------------------------------------------------- City events

class BuildingPlaced:
    def __init__(self, building_id, grid_x, grid_y):
        self.building_id = building_id
        self.grid_x = grid_x
        self.grid_y = grid_y


class BuildingUpgraded:
    def __init__(self, building_id, grid_x, grid_y, new_level):
        self.building_id = building_id
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.new_level = new_level


class BuildingSold:
    def __init__(self, building_id, grid_x, grid_y, refund_gold):
        self.building_id = building_id
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.refund_gold = refund_gold


class CityMilestoneReached:
    def __init__(self, milestone):
        self.milestone = milestone


# ---------------------------------------------------------------- Systems

class IncomeSystem:
    """Adds the city's passive coin income to the city treasury each tick.

    Coins are the city's own currency (kept on the CityState, not the shared
    gold account), so this can simply add the fractional amount every tick.
    """

    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        state.add_coins(state.total_income_per_second() * elapsed_seconds)


class CityMilestoneSystem:
    """Checks every milestone each tick and fires each one exactly once."""

    def __init__(self, milestones):
        self._milestones = list(milestones)

    def tick(self, state, bus: JuiceEventBus):
        for milestone in self._milestones:
            if state.has_reached(milestone.id):
                continue
            if milestone.condition(state):
                state.mark_reached(milestone.id)
                bus.publish(CityMilestoneReached(milestone))


class CityActions:
    """The things the player does: build (gold), upgrade (coins), sell (refund)."""

    def build(self, state, definition, grid_x, grid_y, bus: JuiceEventBus):
        """Place a new building on an empty tile, paid for in gold. Returns False
        if the tile is taken, the building is still locked, or gold is short."""
        if not state.in_bounds(grid_x, grid_y):
            return False
        if not state.is_empty(grid_x, grid_y):
            return False
        # A building type stays locked until the city is big enough.
        if definition.unlock_population > state.total_population():
            return False
        if not state.gold().try_spend(definition.build_cost_gold):
            return False
        instance = BuildingInstance(definition, grid_x, grid_y)
        state.place(instance)
        bus.publish(BuildingPlaced(definition.id, grid_x, grid_y))
        return True

    def upgrade(self, state, instance, bus: JuiceEventBus):
        """Raise a building by one level, paid for in coins (the city's own
        currency). Returns False if it is maxed out or coins are short."""
        if not instance.can_upgrade():
            return False
        cost = instance.upgrade_cost()
        if not state.try_spend_coins(cost):
            return False
        instance.upgrade()
        bus.publish(BuildingUpgraded(
            instance.definition.id, instance.grid_x, instance.grid_y, instance.level()))
        return True

    def sell(self, state, instance, bus: JuiceEventBus):
        """Remove a building and refund part of its build cost as gold."""
        refund = int(instance.definition.build_cost_gold * CityBalance.SELL_REFUND_FRACTION)
        removed = state.remove_building(instance.grid_x, instance.grid_y)
        if not removed:
            return False
        state.gold().credit(refund)
        bus.publish(BuildingSold(
            instance.definition.id, instance.grid_x, instance.grid_y, refund))
        return True
