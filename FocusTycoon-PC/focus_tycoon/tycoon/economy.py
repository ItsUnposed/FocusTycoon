"""The single shared gold account.

Gold is the only currency and it only ever comes from finishing real tasks. There
is no generator, recipe or timer that creates gold. That scarcity is the core of
the whole balance.

This is a simple base class. Real implementations override the three methods.
They must be safe to call from both the simulation thread and the UI thread.
"""

from __future__ import annotations


import threading


class GoldAccount:
    def balance(self):
        raise NotImplementedError("balance() must be implemented by a subclass")

    def credit(self, amount):
        """Add gold (only ever called for a finished-task reward)."""
        raise NotImplementedError("credit() must be implemented by a subclass")

    def try_spend(self, amount):
        """Spend the amount if it is affordable; otherwise return False and change nothing."""
        raise NotImplementedError("try_spend() must be implemented by a subclass")


class Wallet(GoldAccount):
    """A standalone gold account, used when the city runs on its own (no tasks)
    and in tests. Thread-safe."""

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
