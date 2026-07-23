"""City simulation: passive income, milestones and the player build actions.

The simulation runs on a background thread (see core.GameLoop): every tick it
adds a little gold from the city's income buildings and checks whether any
population milestone has just been reached. Building and upgrading happen on the
UI thread through CityActions.

City events (BuildingPlaced, BuildingUpgraded, CityMilestoneReached) are sent on
the shared juice bus so the view can pop up a "+1", play a sound, and so on.
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


class CityMilestoneReached:
    def __init__(self, milestone):
        self.milestone = milestone


# ---------------------------------------------------------------- Systems

class IncomeSystem:
    """Adds the city's passive gold income to the shared balance each tick.

    The shared gold account only stores whole coins, and one tick's worth of
    income is usually a fraction of a coin. So we keep the fractional part in
    `_pending_gold` and only hand over whole coins once they add up.
    """

    def __init__(self):
        self._pending_gold = 0.0

    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        self._pending_gold += state.total_income_per_second() * elapsed_seconds
        if self._pending_gold >= 1.0:
            whole_coins = int(self._pending_gold)
            self._pending_gold -= whole_coins
            state.gold().credit(whole_coins)


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
    """The two things the player does, both paid for with gold: build, upgrade."""

    def build(self, state, definition, grid_x, grid_y, bus: JuiceEventBus):
        """Place a new building on an empty tile. Returns False if the tile is
        taken, the building is still locked, or there is not enough gold."""
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
        """Raise a building by one level, paying its gold cost. Returns False if
        it is maxed out or there is not enough gold."""
        if not instance.can_upgrade():
            return False
        cost = instance.upgrade_cost()
        if not state.gold().try_spend(cost):
            return False
        instance.upgrade()
        bus.publish(BuildingUpgraded(
            instance.definition.id, instance.grid_x, instance.grid_y, instance.level()))
        return True
