"""Hosts the tycoon games and renders whichever one is currently selected.

build_panel(gold_account, saved) builds the embeddable TycoonPanel. It owns the
shared sound and a list of tycoons (the city and the business). The games are no
longer switched with an internal tab navbar - each one is its own entry in the
main top navbar, and the game window calls set_active("business"/"city") to pick
which tycoon this panel draws. Each tycoon keeps its own state and is saved
independently. The class is still named TycoonPanel and the factory build_panel,
so the rest of the app does not need to change.
"""

from __future__ import annotations

from .business_tycoon import BusinessTycoon
from .city_tycoon import CityTycoon
from .ui.tone_player import TonePlayer


class TycoonPanel:
    """Draws the currently selected tycoon (chosen from the main navbar)."""

    def __init__(self, gold, saved):
        self._tone_player = TonePlayer()
        saved_tycoons = saved.tycoons if saved is not None else {}

        # The tycoons this panel can show. The game window picks one with
        # set_active(); "business" is shown first because it comes before Stadt
        # in the navbar.
        self._tycoons = [
            CityTycoon(gold, self._tone_player, saved_tycoons.get("city")),
            BusinessTycoon(gold, self._tone_player, saved_tycoons.get("business")),
        ]
        self._active = self._index_of("business")

    def _index_of(self, name):
        # Find a tycoon by its save-slot name; fall back to the first one.
        for index, tycoon in enumerate(self._tycoons):
            if tycoon.name == name:
                return index
        return 0

    def set_active(self, name):
        # Called from the main navbar when the player picks Business or Stadt.
        self._active = self._index_of(name)

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        # Only the visible tycoon needs its view animated; the others still tick
        # their own simulation on their background threads.
        self._tycoons[self._active].update(elapsed_seconds)

    def render(self, surface, rect):
        # The whole content area belongs to the active tycoon now - there is no
        # internal tab bar to leave room for anymore.
        self._tycoons[self._active].render(surface, rect)

    # ---------- input ----------

    def handle_click(self, position):
        self._tycoons[self._active].handle_click(position)

    def is_over_interactive(self, position):
        return self._tycoons[self._active].is_over_interactive(position)

    def handle_scroll(self, wheel_y, position):
        self._tycoons[self._active].handle_scroll(wheel_y, position)

    def handle_drag(self, position):
        self._tycoons[self._active].handle_drag(position)

    def stop_drag(self):
        self._tycoons[self._active].stop_drag()

    def handle_scroll_key(self, key):
        self._tycoons[self._active].handle_scroll_key(key)

    # ---------- task reward ----------

    def trigger_focus_surge(self, reward_gold):
        # Reward the tycoon the player is currently looking at.
        self._tycoons[self._active].on_task_reward(reward_gold)

    # ---------- debug (the hidden panel) ----------

    def debug_add_coins(self, amount):
        for tycoon in self._tycoons:
            if tycoon.name == "city":
                tycoon.state.add_coins(amount)

    def debug_add_bargeld(self, amount):
        for tycoon in self._tycoons:
            if tycoon.name == "business":
                tycoon.state.earn_bargeld(amount)

    # ---------- sound ----------

    def is_sound_enabled(self):
        return self._tone_player.is_enabled()

    def toggle_sound(self):
        new_state = not self._tone_player.is_enabled()
        self._tone_player.set_enabled(new_state)
        return new_state

    # ---------- lifecycle / persistence ----------

    def shutdown(self):
        for tycoon in self._tycoons:
            tycoon.shutdown()
        self._tone_player.shutdown()

    def save_data(self):
        # One save slot per tycoon, keyed by its name.
        return {tycoon.name: tycoon.save_data() for tycoon in self._tycoons}


def build_panel(shared_gold, saved=None):
    return TycoonPanel(shared_gold, saved)
