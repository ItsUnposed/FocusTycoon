"""Business-tycoon data model.

The business tycoon is a list of small businesses. Each owned business slowly
fills a work cycle; when the cycle is full the player clicks "Collect" to bank
its profit as Cash. Cash is the business tycoon's OWN currency (separate from the
city's Coins): it is spent on upgrading businesses. Gold (earned from tasks) is
spent to BUY new businesses.

Everything here is plain data plus a BusinessState. It is touched by both the
simulation thread (filling cycles) and the UI thread (buying / collecting /
upgrading), so the shared parts are guarded by locks.
"""

from __future__ import annotations

import math
import threading


class BusinessDefinition:
    """The fixed config of one kind of business (lemonade stand, cafe, ...)."""

    def __init__(self, business_id, display_name, buy_cost_gold, base_profit,
                 cycle_seconds, max_level, base_upgrade_cost_cash,
                 upgrade_cost_growth, unlock_cash, accent):
        self.id = business_id
        self.display_name = display_name
        # Gold paid once to buy the business (gold comes from finishing tasks).
        self.buy_cost_gold = buy_cost_gold
        # Cash earned per completed cycle at level 1, and how long a cycle takes.
        self.base_profit = base_profit
        self.cycle_seconds = cycle_seconds
        self.max_level = max_level
        # Upgrading costs Cash and gets more expensive each level.
        self.base_upgrade_cost_cash = base_upgrade_cost_cash
        self.upgrade_cost_growth = upgrade_cost_growth
        # Total Cash the player must have EARNED before this business can be
        # bought (0 means available from the start).
        self.unlock_cash = unlock_cash
        self.accent = accent


class BusinessInstance:
    """One owned business, running its collect cycle. Thread-safe."""

    def __init__(self, definition):
        self.definition = definition
        self._level = 1
        self._progress = 0.0   # 0.0 .. 1.0 across the current cycle
        self._ready = False    # True once the cycle is full and profit waits
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def profit(self):
        # Cash banked when the cycle is collected. Scales with the level.
        with self._lock:
            return self.definition.base_profit * self._level

    def progress(self):
        with self._lock:
            return self._progress

    def is_ready(self):
        with self._lock:
            return self._ready

    def advance(self, elapsed_seconds):
        """Fill the cycle a bit. Returns True if it JUST became ready this tick."""
        with self._lock:
            if self._ready:
                return False
            self._progress += elapsed_seconds / self.definition.cycle_seconds
            if self._progress >= 1.0:
                self._progress = 1.0
                self._ready = True
                return True
            return False

    def collect(self):
        """Bank a full cycle and restart it. Returns the profit, or 0 if not ready."""
        with self._lock:
            if not self._ready:
                return 0.0
            amount = self.definition.base_profit * self._level
            self._ready = False
            self._progress = 0.0
            return amount

    def can_upgrade(self):
        with self._lock:
            return self._level < self.definition.max_level

    def upgrade_cost(self):
        with self._lock:
            if self._level >= self.definition.max_level:
                return 0
            factor = self.definition.upgrade_cost_growth ** (self._level - 1)
            return math.ceil(self.definition.base_upgrade_cost_cash * factor)

    def upgrade(self):
        with self._lock:
            if self._level < self.definition.max_level:
                self._level += 1

    def restore(self, level, progress, ready):
        with self._lock:
            self._level = max(1, min(self.definition.max_level, level))
            self._progress = max(0.0, min(1.0, progress))
            self._ready = bool(ready)


class BusinessState:
    """The whole business tycoon: gold account, Cash, and the owned businesses."""

    def __init__(self, gold):
        self._gold = gold
        self._cash = 0.0
        self._lifetime_cash = 0.0
        self._businesses = {}   # definition id -> BusinessInstance
        self._lock = threading.RLock()

    def gold(self):
        return self._gold

    # ---------- cash (the business tycoon's own currency) ----------

    def cash(self):
        with self._lock:
            return self._cash

    def lifetime_cash(self):
        with self._lock:
            return self._lifetime_cash

    def earn_cash(self, amount):
        if amount <= 0:
            return
        with self._lock:
            self._cash += amount
            self._lifetime_cash += amount

    def try_spend_cash(self, amount):
        with self._lock:
            if self._cash < amount:
                return False
            self._cash -= amount
            return True

    def restore_cash(self, cash, lifetime_cash):
        with self._lock:
            self._cash = max(0.0, cash)
            self._lifetime_cash = max(0.0, lifetime_cash, cash)

    # ---------- the businesses ----------

    def owns(self, business_id):
        with self._lock:
            return business_id in self._businesses

    def business(self, business_id):
        with self._lock:
            return self._businesses.get(business_id)

    def businesses(self):
        with self._lock:
            return dict(self._businesses)

    def add_business(self, instance):
        with self._lock:
            self._businesses[instance.definition.id] = instance

    def profit_per_second(self):
        # A rough "how big is my empire" number: profit divided by cycle length.
        with self._lock:
            total = 0.0
            for instance in self._businesses.values():
                total += instance.profit() / instance.definition.cycle_seconds
            return total
