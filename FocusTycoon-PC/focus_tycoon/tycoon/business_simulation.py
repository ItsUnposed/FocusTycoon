"""Business simulation for the electrical-engineering production chain.

Systems (run on the simulation thread each tick):
- SkillSystem counts down skill level-up cooldowns and finishes them.
- ProductionSystem advances running productions, banks finished stock, rolls for
  machine breakdowns, and drives per-product auto-produce and auto-sell.

Actions (run on the UI thread): level a skill (gold), buy / upgrade / repair a
machine (Bargeld), develop a prototype (Bargeld + skill), start producing a
product (Bargeld material), sell stock (for Bargeld), and buy the two automations.
"""

from __future__ import annotations

import random

from .business_model import MachineInstance
from .juice import JuiceEventBus


class BusinessBalance:
    TICK_RATE_HZ = 8


# ---------------------------------------------------------------- events

class SkillLevelStarted:
    def __init__(self, skill_id):
        self.skill_id = skill_id


class SkillLeveled:
    def __init__(self, skill_id, new_level):
        self.skill_id = skill_id
        self.new_level = new_level


class MachineBought:
    def __init__(self, machine_id):
        self.machine_id = machine_id


class MachineUpgraded:
    def __init__(self, machine_id, new_level):
        self.machine_id = machine_id
        self.new_level = new_level


class MachineBroke:
    def __init__(self, machine_id):
        self.machine_id = machine_id


class MachineRepaired:
    def __init__(self, machine_id):
        self.machine_id = machine_id


class PrototypeDeveloped:
    def __init__(self, prototype_id):
        self.prototype_id = prototype_id


class ProductProduced:
    def __init__(self, product_id, units):
        self.product_id = product_id
        self.units = units


class ProductSold:
    def __init__(self, product_id, amount):
        self.product_id = product_id
        self.amount = amount


class AutomationBought:
    def __init__(self, product_id):
        self.product_id = product_id


class GoldTraded:
    def __init__(self, amount):
        self.amount = amount


# ---------------------------------------------------------------- systems

class SkillSystem:
    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        for instance in state.skills().values():
            if instance.is_leveling():
                was_level = instance.level()
                instance.tick(elapsed_seconds)
                if instance.level() > was_level:
                    bus.publish(SkillLeveled(instance.definition.id, instance.level()))


class ProductionSystem:
    def __init__(self, catalog):
        self._catalog = catalog

    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        for definition_id, line in state.product_lines().items():
            definition = line.definition
            if line.advance(elapsed_seconds):
                # A run just finished: bank the stock and maybe break the machine.
                line.add_stock(definition.units_per_run)
                bus.publish(ProductProduced(definition.id, definition.units_per_run))
                machine = state.machine(definition.required_machine)
                if machine is not None and random.random() < machine.current_break_chance():
                    machine.set_broken(True)
                    bus.publish(MachineBroke(machine.definition.id))
            # Auto-sell whatever is in stock.
            if line.auto_sell() and line.stock() > 0:
                self._sell(state, line, bus)
            # Auto-produce: start a new run when idle and everything is ready.
            if line.auto_produce() and not line.is_producing():
                self._try_start(state, line, bus)

    def _try_start(self, state, line, bus):
        definition = line.definition
        if not self._unlocked(state, definition.id):
            return
        machine = state.machine(definition.required_machine)
        if machine is None or machine.is_broken():
            return
        if not state.try_spend_bargeld(definition.material_cost_bargeld):
            return
        line.start_run()

    def _sell(self, state, line, bus):
        units = line.take_stock()
        if units <= 0:
            return
        amount = units * line.definition.sell_price_bargeld
        state.earn_bargeld(amount)
        bus.publish(ProductSold(line.definition.id, amount))

    def _unlocked(self, state, product_id):
        prototype_id = self._catalog.product_prototype.get(product_id)
        return prototype_id is not None and state.has_prototype(prototype_id)


# ---------------------------------------------------------------- actions

class BusinessActions:
    def __init__(self, catalog):
        self._catalog = catalog

    # ---- bootstrap trade ----

    def trade_gold(self, state, amount, bus: JuiceEventBus):
        traded = state.trade_gold_for_bargeld(amount)
        if traded > 0:
            bus.publish(GoldTraded(traded))
        return traded

    # ---- skills ----

    def level_skill(self, state, instance, bus: JuiceEventBus):
        if not instance.can_level():
            return False
        if not state.gold().try_spend(instance.cost_gold()):
            return False
        instance.start_leveling()
        bus.publish(SkillLevelStarted(instance.definition.id))
        return True

    # ---- machines ----

    def buy_machine(self, state, definition, bus: JuiceEventBus):
        if state.owns_machine(definition.id):
            return False
        if not state.meets_skill(definition.required_skill, definition.required_skill_level):
            return False
        if not state.try_spend_bargeld(definition.buy_cost_bargeld):
            return False
        state.add_machine(MachineInstance(definition))
        bus.publish(MachineBought(definition.id))
        return True

    def upgrade_machine(self, state, instance, bus: JuiceEventBus):
        if not instance.can_upgrade():
            return False
        if not state.try_spend_bargeld(instance.upgrade_cost()):
            return False
        instance.upgrade()
        bus.publish(MachineUpgraded(instance.definition.id, instance.level()))
        return True

    def repair_machine(self, state, instance, bus: JuiceEventBus):
        if not instance.is_broken():
            return False
        if not state.try_spend_bargeld(instance.definition.repair_cost_bargeld):
            return False
        instance.set_broken(False)
        bus.publish(MachineRepaired(instance.definition.id))
        return True

    # ---- prototypes ----

    def develop_prototype(self, state, definition, bus: JuiceEventBus):
        if state.has_prototype(definition.id):
            return False
        if not state.meets_skill(definition.required_skill, definition.required_skill_level):
            return False
        if not state.try_spend_bargeld(definition.cost_bargeld):
            return False
        state.add_prototype(definition.id)
        bus.publish(PrototypeDeveloped(definition.id))
        return True

    # ---- products ----

    def produce_product(self, state, definition, bus: JuiceEventBus):
        line = state.product_line(definition.id)
        if line is None or line.is_producing():
            return False
        prototype_id = self._catalog.product_prototype.get(definition.id)
        if prototype_id is None or not state.has_prototype(prototype_id):
            return False
        machine = state.machine(definition.required_machine)
        if machine is None or machine.is_broken():
            return False
        if not state.try_spend_bargeld(definition.material_cost_bargeld):
            return False
        line.start_run()
        return True

    def sell_product(self, state, definition, bus: JuiceEventBus):
        line = state.product_line(definition.id)
        if line is None:
            return False
        units = line.take_stock()
        if units <= 0:
            return False
        amount = units * definition.sell_price_bargeld
        state.earn_bargeld(amount)
        bus.publish(ProductSold(definition.id, amount))
        return True

    def buy_auto_produce(self, state, definition, bus: JuiceEventBus):
        line = state.product_line(definition.id)
        if line is None or line.auto_produce():
            return False
        if not state.try_spend_bargeld(definition.auto_produce_cost):
            return False
        line.enable_auto_produce()
        bus.publish(AutomationBought(definition.id))
        return True

    def buy_auto_sell(self, state, definition, bus: JuiceEventBus):
        line = state.product_line(definition.id)
        if line is None or line.auto_sell():
            return False
        if not state.try_spend_bargeld(definition.auto_sell_cost):
            return False
        line.enable_auto_sell()
        bus.publish(AutomationBought(definition.id))
        return True
