"""Business tycoon data model: an electrical-engineering startup with a real
production chain.

Resources:
- Gold (from finishing tasks, shared) is spent only on leveling Skills.
- Bargeld (cash) is the firm's money: earned by selling products, spent on
  machines (buy / upgrade / repair), prototypes, production material and
  automation.
- Skills (education) are leveled with Gold and each level-up takes a cooldown.
  Skills gate machines, prototypes and products.

The chain: level Skills -> buy Machines (Bargeld) -> develop Prototypes
(Bargeld + Skills) which unlock Products -> produce a Product (needs its machine
+ Bargeld material) which yields stock -> sell the stock for Bargeld. Machines
can break during production and must be repaired. Producing and selling can be
automated per product for Bargeld.

Everything here is plain data plus a BusinessState, touched by the simulation
thread and the UI thread, so shared parts are guarded by locks.
"""

from __future__ import annotations

import datetime
import math
import threading

# Bargeld a fresh startup begins with, so the very first product can be made.
STARTING_BARGELD = 250.0
# How much gold can be traded 1:1 into Bargeld per real day (a bootstrap so the
# player can get started before any product earns money).
DAILY_TRADE_CAP = 250


def _grown(base, growth, level):
    return math.ceil(base * (growth ** level))


# ---------------------------------------------------------------- skills

class SkillDefinition:
    def __init__(self, skill_id, display_name, base_cost_gold, cost_growth,
                 base_cooldown_seconds, cooldown_growth, max_level, accent):
        self.id = skill_id
        self.display_name = display_name
        self.base_cost_gold = base_cost_gold
        self.cost_growth = cost_growth
        self.base_cooldown_seconds = base_cooldown_seconds
        self.cooldown_growth = cooldown_growth
        self.max_level = max_level
        self.accent = accent


class SkillInstance:
    def __init__(self, definition):
        self.definition = definition
        self._level = 0
        self._leveling = False
        self._remaining = 0.0
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def is_leveling(self):
        with self._lock:
            return self._leveling

    def can_level(self):
        with self._lock:
            return not self._leveling and self._level < self.definition.max_level

    def cost_gold(self):
        with self._lock:
            if self._level >= self.definition.max_level:
                return 0
            return _grown(self.definition.base_cost_gold, self.definition.cost_growth, self._level)

    def cooldown_seconds(self):
        with self._lock:
            return self.definition.base_cooldown_seconds * (self.definition.cooldown_growth ** self._level)

    def remaining_seconds(self):
        with self._lock:
            return self._remaining

    def leveling_fraction(self):
        with self._lock:
            total = self.definition.base_cooldown_seconds * (self.definition.cooldown_growth ** self._level)
            if not self._leveling or total <= 0:
                return 0.0
            return max(0.0, min(1.0, 1.0 - self._remaining / total))

    def start_leveling(self):
        with self._lock:
            if self._leveling or self._level >= self.definition.max_level:
                return
            self._leveling = True
            self._remaining = self.definition.base_cooldown_seconds * (self.definition.cooldown_growth ** self._level)

    def tick(self, elapsed_seconds):
        """Count the cooldown down; finish the level-up when it reaches zero."""
        with self._lock:
            if not self._leveling:
                return
            self._remaining -= elapsed_seconds
            if self._remaining <= 0:
                self._remaining = 0.0
                self._leveling = False
                self._level += 1

    def restore(self, level):
        with self._lock:
            self._level = max(0, min(self.definition.max_level, level))
            self._leveling = False
            self._remaining = 0.0


# ---------------------------------------------------------------- machines

class MachineDefinition:
    def __init__(self, machine_id, display_name, buy_cost_bargeld,
                 base_upgrade_cost_bargeld, upgrade_growth, max_level,
                 required_skill, required_skill_level, break_chance, repair_cost_bargeld, accent):
        self.id = machine_id
        self.display_name = display_name
        self.buy_cost_bargeld = buy_cost_bargeld
        self.base_upgrade_cost_bargeld = base_upgrade_cost_bargeld
        self.upgrade_growth = upgrade_growth
        self.max_level = max_level
        # Buying needs a skill at a level (or None for no requirement).
        self.required_skill = required_skill
        self.required_skill_level = required_skill_level
        # Base chance the machine breaks after a production run (reduced by level).
        self.break_chance = break_chance
        self.repair_cost_bargeld = repair_cost_bargeld
        self.accent = accent


class MachineInstance:
    def __init__(self, definition):
        self.definition = definition
        self._level = 1
        self._broken = False
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def is_broken(self):
        with self._lock:
            return self._broken

    def current_break_chance(self):
        # Higher-level machines are sturdier.
        with self._lock:
            return self.definition.break_chance / self._level

    def can_upgrade(self):
        with self._lock:
            return self._level < self.definition.max_level

    def upgrade_cost(self):
        with self._lock:
            if self._level >= self.definition.max_level:
                return 0
            return _grown(self.definition.base_upgrade_cost_bargeld, self.definition.upgrade_growth, self._level - 1)

    def upgrade(self):
        with self._lock:
            if self._level < self.definition.max_level:
                self._level += 1

    def set_broken(self, broken):
        with self._lock:
            self._broken = broken

    def restore(self, level, broken):
        with self._lock:
            self._level = max(1, min(self.definition.max_level, level))
            self._broken = bool(broken)


# ---------------------------------------------------------------- prototypes

class PrototypeDefinition:
    def __init__(self, prototype_id, display_name, cost_bargeld, required_skill,
                 required_skill_level, unlock_product, accent):
        self.id = prototype_id
        self.display_name = display_name
        self.cost_bargeld = cost_bargeld
        self.required_skill = required_skill
        self.required_skill_level = required_skill_level
        # The product id this prototype unlocks for production.
        self.unlock_product = unlock_product
        self.accent = accent


# ---------------------------------------------------------------- products

class ProductDefinition:
    def __init__(self, product_id, display_name, required_machine, material_cost_bargeld,
                 production_seconds, units_per_run, sell_price_bargeld,
                 auto_produce_cost, auto_sell_cost, accent):
        self.id = product_id
        self.display_name = display_name
        # Producing needs this machine (owned and not broken).
        self.required_machine = required_machine
        self.material_cost_bargeld = material_cost_bargeld
        self.production_seconds = production_seconds
        self.units_per_run = units_per_run
        self.sell_price_bargeld = sell_price_bargeld
        # Bargeld to buy the two automations for this product line.
        self.auto_produce_cost = auto_produce_cost
        self.auto_sell_cost = auto_sell_cost
        self.accent = accent


class ProductLine:
    def __init__(self, definition):
        self.definition = definition
        self._stock = 0
        self._progress = 0.0
        self._producing = False
        self._auto_produce = False
        self._auto_sell = False
        self._lock = threading.RLock()

    def stock(self):
        with self._lock:
            return self._stock

    def progress(self):
        with self._lock:
            return self._progress

    def is_producing(self):
        with self._lock:
            return self._producing

    def auto_produce(self):
        with self._lock:
            return self._auto_produce

    def auto_sell(self):
        with self._lock:
            return self._auto_sell

    def start_run(self):
        with self._lock:
            if self._producing:
                return False
            self._producing = True
            self._progress = 0.0
            return True

    def advance(self, elapsed_seconds):
        """Advance a running production. Returns True if the run JUST finished."""
        with self._lock:
            if not self._producing:
                return False
            self._progress += elapsed_seconds / self.definition.production_seconds
            if self._progress >= 1.0:
                self._progress = 0.0
                self._producing = False
                return True
            return False

    def add_stock(self, units):
        with self._lock:
            self._stock += units

    def take_stock(self):
        with self._lock:
            units = self._stock
            self._stock = 0
            return units

    def enable_auto_produce(self):
        with self._lock:
            self._auto_produce = True

    def enable_auto_sell(self):
        with self._lock:
            self._auto_sell = True

    def restore(self, stock, auto_produce, auto_sell):
        with self._lock:
            self._stock = max(0, stock)
            self._auto_produce = bool(auto_produce)
            self._auto_sell = bool(auto_sell)


# ---------------------------------------------------------------- the state

class BusinessState:
    def __init__(self, gold, catalog):
        self._gold = gold
        self._bargeld = STARTING_BARGELD
        self._skills = {s.id: SkillInstance(s) for s in catalog.skills}
        self._machines = {}
        self._prototypes = set()
        self._products = {p.id: ProductLine(p) for p in catalog.products}
        # Daily Gold->Bargeld trading (a bootstrap): how much was traded today.
        self._traded_today = 0
        self._trade_date = ""
        self._lock = threading.RLock()

    def gold(self):
        return self._gold

    # ---------- Gold -> Bargeld trading (capped per day) ----------

    def _refresh_trade_day(self):
        today = datetime.date.today().isoformat()
        if self._trade_date != today:
            self._trade_date = today
            self._traded_today = 0

    def remaining_trades_today(self):
        with self._lock:
            self._refresh_trade_day()
            return max(0, DAILY_TRADE_CAP - self._traded_today)

    def trade_gold_for_bargeld(self, amount):
        """Trade up to `amount` gold 1:1 into Bargeld, within today's cap and the
        gold on hand. Returns how much was actually traded."""
        with self._lock:
            self._refresh_trade_day()
            allowed = min(int(amount), DAILY_TRADE_CAP - self._traded_today, int(self._gold.balance()))
            if allowed <= 0:
                return 0
            if not self._gold.try_spend(allowed):
                return 0
            self._bargeld += allowed
            self._traded_today += allowed
            return allowed

    def traded_today(self):
        with self._lock:
            return self._traded_today

    def trade_date(self):
        with self._lock:
            return self._trade_date

    def restore_trades(self, traded_today, trade_date):
        with self._lock:
            self._trade_date = str(trade_date) if trade_date else ""
            self._traded_today = max(0, traded_today)

    # ---------- Bargeld ----------

    def bargeld(self):
        with self._lock:
            return self._bargeld

    def earn_bargeld(self, amount):
        if amount <= 0:
            return
        with self._lock:
            self._bargeld += amount

    def try_spend_bargeld(self, amount):
        with self._lock:
            if self._bargeld < amount:
                return False
            self._bargeld -= amount
            return True

    def restore_bargeld(self, amount):
        with self._lock:
            self._bargeld = max(0.0, amount)

    # ---------- skills ----------

    def skill(self, skill_id):
        with self._lock:
            return self._skills.get(skill_id)

    def skills(self):
        with self._lock:
            return dict(self._skills)

    def skill_level(self, skill_id):
        with self._lock:
            instance = self._skills.get(skill_id)
            return instance.level() if instance is not None else 0

    def meets_skill(self, skill_id, min_level):
        if skill_id is None:
            return True
        return self.skill_level(skill_id) >= min_level

    # ---------- machines ----------

    def owns_machine(self, machine_id):
        with self._lock:
            return machine_id in self._machines

    def machine(self, machine_id):
        with self._lock:
            return self._machines.get(machine_id)

    def machines(self):
        with self._lock:
            return dict(self._machines)

    def add_machine(self, instance):
        with self._lock:
            self._machines[instance.definition.id] = instance

    # ---------- prototypes ----------

    def has_prototype(self, prototype_id):
        with self._lock:
            return prototype_id in self._prototypes

    def prototype_ids(self):
        with self._lock:
            return set(self._prototypes)

    def add_prototype(self, prototype_id):
        with self._lock:
            self._prototypes.add(prototype_id)

    # ---------- products ----------

    def product_line(self, product_id):
        with self._lock:
            return self._products.get(product_id)

    def product_lines(self):
        with self._lock:
            return dict(self._products)
