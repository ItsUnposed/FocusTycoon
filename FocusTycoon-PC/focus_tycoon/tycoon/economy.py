"""The single shared gold account.

Gold is the only currency and it only ever comes from finishing real tasks. There
is no generator, recipe or timer that creates gold. That scarcity is the core of
the whole balance.

This is a simple base class. Real implementations override the three methods.
They must be safe to call from both the simulation thread and the UI thread.
"""

from __future__ import annotations


class GoldAccount:
    def balance(self):
        raise NotImplementedError("balance() must be implemented by a subclass")

    def credit(self, amount):
        """Add gold (only ever called for a finished-task reward)."""
        raise NotImplementedError("credit() must be implemented by a subclass")

    def try_spend(self, amount):
        """Spend the amount if it is affordable; otherwise return False and change nothing."""
        raise NotImplementedError("try_spend() must be implemented by a subclass")
