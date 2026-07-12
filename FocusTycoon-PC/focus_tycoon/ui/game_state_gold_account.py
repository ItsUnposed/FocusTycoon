"""Bridge between the task-side gold and the Tycoon gold account.

The floating-island producers spend from - and finished-task rewards flow into -
one shared balance. Gold is a whole number on the task side, but the Tycoon works
with decimals: spends round up (never let the player cheer for a fraction of gold
they do not have) and credits round to the nearest whole coin.
"""

from __future__ import annotations

import math

from ..model.game_state import GameState
from ..tycoon.economy import GoldAccount


class GameStateGoldAccount(GoldAccount):
    def __init__(self, game: GameState):
        self._game = game

    def balance(self):
        return self._game.get_gold()

    def credit(self, amount):
        # Round to the nearest whole coin when adding gold earned in the Tycoon.
        self._game.add_gold(round(amount))

    def try_spend(self, amount):
        # Round the cost up, so the player never gets to spend a fraction of a
        # coin they do not actually have.
        return self._game.spend_gold(math.ceil(amount))
