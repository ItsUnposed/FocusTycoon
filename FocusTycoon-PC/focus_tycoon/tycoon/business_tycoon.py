"""The business tycoon: an electrical-engineering startup with a real production
chain, on the Tycoon page.

It owns its own simulation (skill cooldowns + production), state, view and HUD,
and exposes the same small interface as the city tycoon so the parent TycoonPanel
can switch to it with the main tab navbar. Inside, a row of sub-tabs switches
between Education, Machines, Prototypes and Products.
"""

from __future__ import annotations

import pygame

from ..i18n import translate
from ..util import ui_fonts
from .business_content import build_catalog, build_initial_state
from .business_model import MachineInstance
from .business_simulation import (BusinessActions, BusinessBalance, ProductionSystem,
                                 SkillSystem)
from .core import GameLoop
from .juice import JuiceEventBus
from .ui.business_hud import BusinessHud, HEIGHT as HUD_HEIGHT
from .ui.business_view import (BusinessView, SECTION_MACHINES, SECTION_PRODUCTS,
                             SECTION_PROTOTYPES, SECTION_SKILLS)

SUBTAB_HEIGHT = 40
SUBTAB_BG = (14, 15, 24)
SUBTAB_ACTIVE = (140, 220, 150)
SUBTAB_CARD = (34, 37, 52)
SUBTAB_CARD_HI = (46, 50, 68)
INK = (236, 238, 248)
BG = (12, 13, 22)

_SECTIONS = [
    (SECTION_SKILLS, "biz_tab_education"),
    (SECTION_MACHINES, "biz_tab_machines"),
    (SECTION_PROTOTYPES, "biz_tab_prototypes"),
    (SECTION_PRODUCTS, "biz_tab_products"),
]

# How much gold one click of the bootstrap trade converts (capped per day).
TRADE_BATCH = 50
GOLD = (245, 205, 96)


class BusinessTycoon:
    name = "business"
    title_key = "tycoon_tab_business"

    def __init__(self, gold, sound, saved_data):
        self._catalog = build_catalog()
        self.state = build_initial_state(gold, self._catalog)
        if saved_data is not None:
            self._load_data(saved_data)

        self._bus = JuiceEventBus()
        actions = BusinessActions(self._catalog)
        skill_system = SkillSystem()
        production_system = ProductionSystem(self._catalog)

        def tick(elapsed_seconds):
            skill_system.tick(elapsed_seconds, self.state, self._bus)
            production_system.tick(elapsed_seconds, self.state, self._bus)

        self._game_loop = GameLoop(BusinessBalance.TICK_RATE_HZ, tick)
        self._actions = actions
        self._hud = BusinessHud(self.state, self._catalog)
        self._view = BusinessView(self.state, actions, self._bus, sound, self._catalog)
        self._subtab_rects = []
        self._trade_button_rect = pygame.Rect(0, 0, 0, 0)
        self._game_loop.start()

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        pass

    def render(self, surface, rect):
        hud_rect = pygame.Rect(rect.x, rect.y, rect.width, HUD_HEIGHT)
        subtab_rect = pygame.Rect(rect.x, rect.y + HUD_HEIGHT, rect.width, SUBTAB_HEIGHT)
        body = pygame.Rect(rect.x, subtab_rect.bottom, rect.width, rect.height - HUD_HEIGHT - SUBTAB_HEIGHT)

        surface.fill((16, 17, 27), body)
        self._hud.render(surface, hud_rect)
        self._draw_subtabs(surface, subtab_rect)
        self._view.render(surface, body)

    def _draw_subtabs(self, surface, rect):
        surface.fill(SUBTAB_BG, rect)
        surface.fill((40, 42, 60), (rect.x, rect.bottom - 1, rect.width, 1))
        self._subtab_rects = []
        x = rect.x + 16
        for section, key in _SECTIONS:
            label = translate(key)
            width = ui_fonts.base(13, bold=True).size(label)[0] + 30
            tab_rect = pygame.Rect(x, rect.y + 7, width, SUBTAB_HEIGHT - 14)
            active = self._view.section == section
            if active:
                color, text_color = SUBTAB_ACTIVE, BG
            elif tab_rect.collidepoint(pygame.mouse.get_pos()):
                color, text_color = SUBTAB_CARD_HI, INK
            else:
                color, text_color = SUBTAB_CARD, INK
            pygame.draw.rect(surface, color, tab_rect, border_radius=tab_rect.height // 2)
            text = ui_fonts.base(13, bold=True).render(label, True, text_color)
            surface.blit(text, (tab_rect.centerx - text.get_width() // 2, tab_rect.centery - text.get_height() // 2))
            self._subtab_rects.append((tab_rect, section))
            x += width + 8

        # A right-aligned "trade gold for Bargeld" button (the bootstrap).
        remaining = self.state.remaining_trades_today()
        label = translate("biz_trade").format(remaining=remaining)
        button_width = ui_fonts.base(12, bold=True).size(label)[0] + 28
        button = pygame.Rect(rect.right - button_width - 12, rect.y + 7, button_width, SUBTAB_HEIGHT - 14)
        enabled = remaining > 0 and self.state.gold().balance() >= 1
        hover = button.collidepoint(pygame.mouse.get_pos())
        if not enabled:
            fill, text_color = SUBTAB_CARD, (120, 124, 148)
        else:
            fill, text_color = (SUBTAB_CARD_HI if hover else SUBTAB_CARD), GOLD
        pygame.draw.rect(surface, fill, button, border_radius=button.height // 2)
        pygame.draw.rect(surface, GOLD if enabled else (60, 64, 88), button, width=1, border_radius=button.height // 2)
        text = ui_fonts.base(12, bold=True).render(label, True, text_color)
        surface.blit(text, (button.centerx - text.get_width() // 2, button.centery - text.get_height() // 2))
        self._trade_button_rect = button

    # ---------- input ----------

    def handle_click(self, position):
        if self._trade_button_rect.collidepoint(position):
            self._actions.trade_gold(self.state, TRADE_BATCH, self._bus)
            return
        for tab_rect, section in self._subtab_rects:
            if tab_rect.collidepoint(position):
                self._view.section = section
                return
        self._view.handle_click(position)

    def is_over_interactive(self, position):
        if self._trade_button_rect.collidepoint(position):
            return True
        for tab_rect, _ in self._subtab_rects:
            if tab_rect.collidepoint(position):
                return True
        return self._view.is_over(position)

    # ---------- task reward / lifecycle ----------

    def on_task_reward(self, reward_gold):
        pass

    def shutdown(self):
        self._game_loop.stop()
        self._hud.stop()

    # ---------- persistence ----------

    def save_data(self):
        skills = {sid: inst.level() for sid, inst in self.state.skills().items()}
        machines = []
        for instance in self.state.machines().values():
            machines.append({"id": instance.definition.id, "level": instance.level(),
                             "broken": instance.is_broken()})
        products = []
        for pid, line in self.state.product_lines().items():
            if line.stock() > 0 or line.auto_produce() or line.auto_sell():
                products.append({"id": pid, "stock": line.stock(),
                                 "auto_produce": line.auto_produce(), "auto_sell": line.auto_sell()})
        return {
            "bargeld": round(self.state.bargeld(), 2),
            "skills": skills,
            "machines": machines,
            "prototypes": list(self.state.prototype_ids()),
            "products": products,
            "tradedToday": self.state.traded_today(),
            "tradeDate": self.state.trade_date(),
        }

    def _load_data(self, data):
        bargeld = data.get("bargeld")
        if _is_number(bargeld):
            self.state.restore_bargeld(float(bargeld))
        traded = data.get("tradedToday")
        self.state.restore_trades(traded if _is_int(traded) else 0, data.get("tradeDate", ""))
        if isinstance(data.get("skills"), dict):
            for skill_id, level in data["skills"].items():
                instance = self.state.skill(str(skill_id))
                if instance is not None and _is_int(level):
                    instance.restore(level)
        if isinstance(data.get("prototypes"), list):
            for prototype_id in data["prototypes"]:
                if str(prototype_id) in self._catalog.prototype_by_id:
                    self.state.add_prototype(str(prototype_id))
        if isinstance(data.get("machines"), list):
            for item in data["machines"]:
                if not isinstance(item, dict):
                    continue
                definition = self._catalog.machine_by_id.get(str(item.get("id", "")))
                if definition is None or self.state.owns_machine(definition.id):
                    continue
                instance = MachineInstance(definition)
                level = item.get("level")
                instance.restore(level if _is_int(level) else 1, item.get("broken") is True)
                self.state.add_machine(instance)
        if isinstance(data.get("products"), list):
            for item in data["products"]:
                if not isinstance(item, dict):
                    continue
                line = self.state.product_line(str(item.get("id", "")))
                if line is None:
                    continue
                stock = item.get("stock")
                line.restore(stock if _is_int(stock) else 0,
                             item.get("auto_produce") is True, item.get("auto_sell") is True)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
