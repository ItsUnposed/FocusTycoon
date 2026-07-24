"""The business tycoon: a second, fully separate tycoon on the Tycoon page.

Like CityTycoon it owns its own simulation loop, state, view and HUD and exposes
the same small interface, so the parent TycoonPanel can switch between them with
the tab navbar. Its currency (Cash) is entirely separate from the city's Coins;
only gold (from tasks) is shared, and only for buying businesses.
"""

from __future__ import annotations

import pygame

from .business_content import build_catalog, build_initial_state
from .business_simulation import BusinessActions, BusinessBalance, ProgressSystem
from .core import GameLoop
from .juice import JuiceEventBus
from .ui.business_hud import BusinessHud, HEIGHT as HUD_HEIGHT
from .ui.business_view import BusinessView


class BusinessTycoon:
    name = "business"
    title_key = "tycoon_tab_business"

    def __init__(self, gold, sound, saved_data):
        self._catalog = build_catalog()
        self.state = build_initial_state(gold)
        if saved_data is not None:
            self._load_data(saved_data)

        self._bus = JuiceEventBus()
        actions = BusinessActions()
        progress_system = ProgressSystem()

        def tick(elapsed_seconds):
            progress_system.tick(elapsed_seconds, self.state, self._bus)

        self._game_loop = GameLoop(BusinessBalance.TICK_RATE_HZ, tick)
        self._hud = BusinessHud(self.state, self._catalog)
        self._view = BusinessView(self.state, actions, self._bus, sound, self._catalog)
        self._game_loop.start()

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        pass  # the list has no animation of its own; the bars follow the state

    def render(self, surface, rect):
        hud_rect = pygame.Rect(rect.x, rect.y, rect.width, HUD_HEIGHT)
        list_rect = pygame.Rect(rect.x, rect.y + HUD_HEIGHT, rect.width, rect.height - HUD_HEIGHT)
        # A dark background behind the card list.
        surface.fill((16, 17, 27), list_rect)
        self._hud.render(surface, hud_rect)
        self._view.render(surface, list_rect)

    # ---------- input ----------

    def handle_click(self, position):
        self._view.handle_click(position)

    def is_over_interactive(self, position):
        return self._view.is_over(position)

    # ---------- task reward / lifecycle ----------

    def on_task_reward(self, reward_gold):
        pass  # the business celebration is left simple for now

    def shutdown(self):
        self._game_loop.stop()
        self._hud.stop()

    # ---------- persistence ----------

    def save_data(self):
        businesses = []
        for instance in self.state.businesses().values():
            businesses.append({
                "id": instance.definition.id,
                "level": instance.level(),
                "progress": round(instance.progress(), 3),
                "ready": instance.is_ready(),
            })
        return {
            "businesses": businesses,
            "cash": round(self.state.cash(), 2),
            "lifetime": round(self.state.lifetime_cash(), 2),
        }

    def _load_data(self, data):
        from .business_model import BusinessInstance
        by_id = {definition.id: definition for definition in self._catalog}
        cash = data.get("cash")
        lifetime = data.get("lifetime")
        self.state.restore_cash(
            float(cash) if _is_number(cash) else 0.0,
            float(lifetime) if _is_number(lifetime) else 0.0)
        if isinstance(data.get("businesses"), list):
            for item in data["businesses"]:
                if not isinstance(item, dict):
                    continue
                definition = by_id.get(str(item.get("id", "")))
                if definition is None or self.state.owns(definition.id):
                    continue
                instance = BusinessInstance(definition)
                level = item.get("level")
                progress = item.get("progress")
                instance.restore(
                    level if _is_int(level) else 1,
                    float(progress) if _is_number(progress) else 0.0,
                    item.get("ready") is True)
                self.state.add_business(instance)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
