"""Business simulation: filling cycles and the player actions (buy / collect / upgrade).

The simulation thread fills each owned business's cycle a little every tick and
fires a BusinessReady event when one is ready to collect. Buying, collecting and
upgrading happen on the UI thread through BusinessActions. All player-visible
moments go out on the shared juice bus so the view can react.
"""

from __future__ import annotations

from .business_model import BusinessInstance
from .juice import JuiceEventBus


class BusinessBalance:
    # Simulation ticks per second (rendering runs on its own timer).
    TICK_RATE_HZ = 8


# ---------------------------------------------------------------- events

class BusinessBought:
    def __init__(self, business_id):
        self.business_id = business_id


class BusinessCollected:
    def __init__(self, business_id, amount):
        self.business_id = business_id
        self.amount = amount


class BusinessUpgraded:
    def __init__(self, business_id, new_level):
        self.business_id = business_id
        self.new_level = new_level


class BusinessReady:
    def __init__(self, business_id):
        self.business_id = business_id


# ---------------------------------------------------------------- systems

class ProgressSystem:
    """Fills every owned business's cycle each tick."""

    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        for instance in state.businesses().values():
            just_ready = instance.advance(elapsed_seconds)
            if just_ready:
                bus.publish(BusinessReady(instance.definition.id))


class BusinessActions:
    """The player actions: buy (gold), collect (cash in), upgrade (cash out)."""

    def buy(self, state, definition, bus: JuiceEventBus):
        """Buy a business with gold. Returns False if already owned, still locked,
        or there is not enough gold."""
        if state.owns(definition.id):
            return False
        if definition.unlock_cash > state.lifetime_cash():
            return False
        if not state.gold().try_spend(definition.buy_cost_gold):
            return False
        state.add_business(BusinessInstance(definition))
        bus.publish(BusinessBought(definition.id))
        return True

    def collect(self, state, instance, bus: JuiceEventBus):
        """Bank a ready business's profit as Cash. Returns the amount collected."""
        amount = instance.collect()
        if amount <= 0:
            return 0.0
        state.earn_cash(amount)
        bus.publish(BusinessCollected(instance.definition.id, amount))
        return amount

    def collect_all(self, state, bus: JuiceEventBus):
        """Collect every business that is ready. Returns the total collected."""
        total = 0.0
        for instance in state.businesses().values():
            total += self.collect(state, instance, bus)
        return total

    def upgrade(self, state, instance, bus: JuiceEventBus):
        """Raise a business by one level, paid for in Cash. Returns False if it is
        maxed out or there is not enough Cash."""
        if not instance.can_upgrade():
            return False
        cost = instance.upgrade_cost()
        if not state.try_spend_cash(cost):
            return False
        instance.upgrade()
        bus.publish(BusinessUpgraded(instance.definition.id, instance.level()))
        return True
