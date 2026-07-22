"""Simulation: production, cheering / upgrading / unlocking and milestones.

Important change in this version: refineries no longer consume raw resources.
Every producer simply makes its own resource. Resources are ONLY spent on
upgrades, never when you deploy or cheer another producer. This removes the
confusing "my points went down when I started another minion" effect.

The bottleneck is now purely gold: cheering (filling the tank) costs gold, and
gold only comes from finishing real tasks.
"""

from __future__ import annotations

from . import juice
from .juice import JuiceEventBus


class BalancingConfig:
    """Central tuning numbers.

    The economy is tuned so that maxing out the whole Tycoon takes a long time
    (about 50 to 100 days) if the player finishes one or two full tasks per day.
    """

    # A rough yardstick: how much gold a normal day of tasks is worth.
    REFERENCE_DAILY_GOLD = 500.0
    # Seconds a full tank lasts by default (5x longer than before).
    DEFAULT_FUEL_BURN_SECONDS = 110.0
    # Output multiplier while a producer has no fuel - keeps a tiny trickle alive.
    PASSIVE_OUTPUT_RATIO_DEFAULT = 0.02
    # Simulation ticks per second. Rendering runs on its own timer.
    TICK_RATE_HZ = 8
    # Minimum built-up output before a "resource produced" juice event fires.
    RESOURCE_JUICE_PULSE_THRESHOLD = 1.0
    # Gold a fresh player starts with when the map runs standalone.
    STANDALONE_STARTING_GOLD = 300.0

    # ---- Focus Surge: the reward for finishing a real task ----
    # While a surge is running, every producer runs this many times faster than
    # its normal slow trickle.
    SURGE_ACTIVE_MULTIPLIER = 5.0
    # Each point of gold a finished task was worth adds this many seconds of
    # surge, so a bigger task keeps the islands humming for longer.
    SURGE_SECONDS_PER_GOLD = 0.2
    # The surge timer can never hold more than this, so a huge batch of tasks
    # does not buy hours of boost at once.
    SURGE_MAX_SECONDS = 600.0


class ProductionSystem:
    """Runs every tick: drains fuel and produces resources."""

    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        # Let the Focus Surge run down a little each tick, then work out how much
        # faster everything runs right now (5x while surging, 1x otherwise).
        state.drain_surge(elapsed_seconds)
        surge_multiplier = state.surge_multiplier(BalancingConfig.SURGE_ACTIVE_MULTIPLIER)
        for sector in state.sectors().values():
            if not sector.is_unlocked():
                continue
            for generator in sector.generators():
                generator.drain_fuel(elapsed_seconds)
                self._produce(generator, elapsed_seconds, surge_multiplier, state.inventory(), bus)

    def _produce(self, generator, elapsed_seconds, surge_multiplier, inventory, bus: JuiceEventBus):
        definition = generator.definition
        # The surge speeds up every producer by the same factor.
        units_produced = generator.current_output_per_second() * surge_multiplier * elapsed_seconds
        if units_produced <= 0:
            return

        if definition.is_refinery():
            # Refineries no longer eat raw materials - they just produce output.
            recipe = definition.recipe
            output_amount = units_produced * recipe.output_per_unit
            inventory.add(recipe.output, output_amount)
            generator.add_unpulsed_output(output_amount)
            pulsed = generator.drain_pulse_if_ready(BalancingConfig.RESOURCE_JUICE_PULSE_THRESHOLD)
            if pulsed > 0:
                bus.publish(juice.RecipeCompleted(
                    generator.instance_id, generator.position, recipe, pulsed))
        else:
            inventory.add(definition.output_resource, units_produced)
            generator.add_unpulsed_output(units_produced)
            pulsed = generator.drain_pulse_if_ready(BalancingConfig.RESOURCE_JUICE_PULSE_THRESHOLD)
            if pulsed > 0:
                bus.publish(juice.ResourceProduced(
                    generator.instance_id, generator.position,
                    definition.output_resource, pulsed))


class FuelingService:
    """The three player actions that spend something: cheer, upgrade, unlock."""

    def ignite(self, state, generator, bus: JuiceEventBus):
        """Cheer a producer: spend gold, fill the tank to full. Returns False if gold is short."""
        cost = generator.definition.fuel_cost_gold
        if not state.gold().try_spend(cost):
            return False
        generator.ignite()
        bus.publish(juice.GeneratorFueled(generator.instance_id, generator.position, cost))
        return True

    def upgrade(self, state, generator, bus: JuiceEventBus):
        """Raise a producer's level. This is the ONLY action that spends resources."""
        if not generator.can_upgrade():
            return False
        cost = generator.upgrade_cost_at_current_level()
        # Check and pay in one step, so the simulation thread cannot make us go negative.
        if not state.inventory().try_remove_all(cost):
            return False
        generator.upgrade()
        bus.publish(juice.GeneratorUpgraded(
            generator.instance_id, generator.position, generator.level()))
        return True

    def unlock_sector(self, state, sector, bus: JuiceEventBus):
        """Unlock a sector: spend gold once, then it stays unlocked forever."""
        if sector.is_unlocked():
            return True
        if not state.gold().try_spend(sector.definition.unlock_cost):
            return False
        sector.unlock()
        bus.publish(juice.SectorUnlocked(sector.definition.id, sector.definition.origin))
        return True


class MilestoneSystem:
    """Checks all milestones every tick and fires each one exactly once."""

    def __init__(self, milestones):
        self._milestones = list(milestones)

    def tick(self, state, bus: JuiceEventBus):
        for milestone in self._milestones:
            if state.has_reached(milestone.id):
                continue
            if milestone.condition(state):
                state.mark_reached(milestone.id)
                bus.publish(juice.MilestoneReached(milestone))
