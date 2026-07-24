"""The business-tycoon view: a vertical list of business cards (for pygame).

Each owned business shows a progress bar that fills over its cycle; when it is
full the player clicks "Collect" (or the card) to bank its Cash. A card also has
an "Upgrade" button (paid in Cash). Businesses the player does not own yet show a
"Buy" button (paid in gold), or a locked note until enough Cash has been earned.

Everything is drawn at native size (no scaled surface), so the text stays crisp.
"""

from __future__ import annotations

import pygame

from ...i18n import translate
from ...util import ui_fonts
from ..business_simulation import BusinessBought, BusinessCollected, BusinessReady

INK = (236, 238, 248)
MUTED = (168, 172, 194)
GOLD = (245, 205, 96)
CASH = (140, 220, 150)
CARD = (34, 37, 52)
CARD_HI = (46, 50, 68)
ACCENT = (122, 196, 255)
SUCCESS = (120, 214, 150)
DANGER = (226, 130, 130)
DISABLED = (58, 62, 82)
TRACK = (44, 48, 66)

CARD_HEIGHT = 82
CARD_GAP = 8
HEADER_HEIGHT = 34


def localized_business_name(definition):
    key = "business_" + definition.id
    name = translate(key)
    return definition.display_name if name == key else name


class BusinessView:
    def __init__(self, state, actions, bus, sound, catalog):
        self.state = state
        self.actions = actions
        self.bus = bus
        self.sound = sound
        self.catalog = catalog
        bus.subscribe(self.on_juice_event)
        # Rebuilt every frame: (rect, kind, payload) for hit-testing.
        self._buttons = []

    # ---------- sound feedback ----------

    def on_juice_event(self, event):
        if isinstance(event, BusinessCollected):
            self.sound.play_note(659, 0.09, True)
        elif isinstance(event, BusinessBought):
            self.sound.play_note(523, 0.10, False)
        elif isinstance(event, BusinessReady):
            self.sound.play_note(440, 0.07, True)

    # ---------- input ----------

    def handle_click(self, position):
        for rect, kind, payload in self._buttons:
            if not rect.collidepoint(position):
                continue
            if kind == "collect_all":
                self.actions.collect_all(self.state, self.bus)
            elif kind in ("collect", "collect_body"):
                self.actions.collect(self.state, payload, self.bus)
            elif kind == "upgrade":
                self.actions.upgrade(self.state, payload, self.bus)
            elif kind == "buy":
                self.actions.buy(self.state, payload, self.bus)
            return

    def is_over(self, position):
        for rect, _, _ in self._buttons:
            if rect.collidepoint(position):
                return True
        return False

    # ---------- painting ----------

    def render(self, surface, rect):
        self._buttons = []
        x = rect.x + 16
        width = rect.width - 32

        # "Collect all" button at the top.
        total_ready = 0.0
        for instance in self.state.businesses().values():
            if instance.is_ready():
                total_ready += instance.profit()
        header_rect = pygame.Rect(x, rect.y + 10, width, HEADER_HEIGHT)
        self._draw_collect_all(surface, header_rect, total_ready)

        y = header_rect.bottom + 10
        for definition in self.catalog:
            card_rect = pygame.Rect(x, y, width, CARD_HEIGHT)
            self._draw_card(surface, card_rect, definition)
            y += CARD_HEIGHT + CARD_GAP

    def _draw_collect_all(self, surface, rect, total_ready):
        enabled = total_ready > 0
        mouse_pos = pygame.mouse.get_pos()
        if not enabled:
            fill, text_color = DISABLED, MUTED
        elif rect.collidepoint(mouse_pos):
            fill, text_color = (70, 150, 100), (255, 255, 255)
        else:
            fill, text_color = (54, 120, 82), (235, 255, 240)
        pygame.draw.rect(surface, fill, rect, border_radius=10)
        if enabled:
            label = translate("biz_collect_all").format(amount=int(total_ready))
        else:
            label = translate("biz_collect_all_idle")
        text = ui_fonts.base(13, bold=True).render(label, True, text_color)
        surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))
        self._buttons.append((rect, "collect_all", None))

    def _draw_card(self, surface, rect, definition):
        instance = self.state.business(definition.id)
        owned = instance is not None
        locked = (not owned) and definition.unlock_cash > self.state.lifetime_cash()

        pygame.draw.rect(surface, CARD if owned else (26, 28, 40), rect, border_radius=12)
        pygame.draw.rect(surface, (60, 64, 88), rect, width=1, border_radius=12)

        # Colour swatch on the left.
        accent = definition.accent if owned else _dim(definition.accent)
        swatch = pygame.Rect(rect.x + 12, rect.y + 14, 54, 54)
        pygame.draw.rect(surface, accent, swatch, border_radius=10)
        pygame.draw.rect(surface, _dark(accent), swatch, width=1, border_radius=10)

        name = localized_business_name(definition)
        name_color = INK if owned else MUTED
        surface.blit(ui_fonts.base(15, bold=True).render(name, True, name_color), (rect.x + 80, rect.y + 12))

        if owned:
            self._draw_owned_card(surface, rect, instance)
        else:
            self._draw_unowned_card(surface, rect, definition, locked)

    def _draw_owned_card(self, surface, rect, instance):
        definition = instance.definition
        info = translate("biz_owned_info").format(
            level=instance.level(), profit=instance.profit(), cycle=_num(definition.cycle_seconds))
        surface.blit(ui_fonts.base(12).render(info, True, MUTED), (rect.x + 80, rect.y + 36))

        # Two action buttons on the right: Collect and Upgrade.
        upgrade_rect = pygame.Rect(rect.right - 12 - 150, rect.y + 14, 150, 26)
        collect_rect = pygame.Rect(rect.right - 12 - 150, rect.y + 44, 150, 26)
        self._draw_upgrade_button(surface, upgrade_rect, instance)
        self._draw_collect_button(surface, collect_rect, instance)

        # Progress bar fills the space between the name and the buttons.
        bar_left = rect.x + 80
        bar_right = collect_rect.left - 14
        bar = pygame.Rect(bar_left, rect.y + 56, max(20, bar_right - bar_left), 12)
        pygame.draw.rect(surface, TRACK, bar, border_radius=6)
        ready = instance.is_ready()
        fill_fraction = 1.0 if ready else instance.progress()
        if fill_fraction > 0:
            fill_width = max(6, int(bar.width * fill_fraction))
            pygame.draw.rect(surface, SUCCESS if ready else ACCENT,
                             pygame.Rect(bar.x, bar.y, fill_width, bar.height), border_radius=6)
        if ready:
            ready_text = ui_fonts.base(11, bold=True).render(translate("biz_ready"), True, (18, 22, 30))
            surface.blit(ready_text, (bar.centerx - ready_text.get_width() // 2, bar.y - 1))
            # The whole ready card is clickable to collect (checked after buttons).
            self._buttons.append((rect, "collect_body", instance))

    def _draw_unowned_card(self, surface, rect, definition, locked):
        info = translate("biz_unowned_info").format(
            profit=definition.base_profit, cycle=_num(definition.cycle_seconds))
        surface.blit(ui_fonts.base(12).render(info, True, MUTED), (rect.x + 80, rect.y + 36))

        buy_rect = pygame.Rect(rect.right - 12 - 190, rect.centery - 17, 190, 34)
        mouse_pos = pygame.mouse.get_pos()
        if locked:
            pygame.draw.rect(surface, DISABLED, buy_rect, border_radius=10)
            label = translate("biz_locked").format(cash=int(definition.unlock_cash))
            color = MUTED
        else:
            affordable = self.state.gold().balance() >= definition.buy_cost_gold
            hover = buy_rect.collidepoint(mouse_pos)
            pygame.draw.rect(surface, CARD_HI if hover else (46, 66, 52), buy_rect, border_radius=10)
            pygame.draw.rect(surface, SUCCESS if affordable else DANGER, buy_rect, width=1, border_radius=10)
            label = translate("biz_buy").format(gold=int(definition.buy_cost_gold))
            color = (210, 245, 220) if affordable else (240, 205, 205)
            self._buttons.append((buy_rect, "buy", definition))
        text = ui_fonts.base(12, bold=True).render(label, True, color)
        surface.blit(text, (buy_rect.centerx - text.get_width() // 2, buy_rect.centery - text.get_height() // 2))

    def _draw_collect_button(self, surface, rect, instance):
        ready = instance.is_ready()
        mouse_pos = pygame.mouse.get_pos()
        if not ready:
            pygame.draw.rect(surface, DISABLED, rect, border_radius=8)
            text_color = MUTED
            label = translate("biz_collect").format(amount=int(instance.profit()))
        else:
            hover = rect.collidepoint(mouse_pos)
            pygame.draw.rect(surface, (70, 150, 100) if hover else (54, 120, 82), rect, border_radius=8)
            text_color = (255, 255, 255)
            label = translate("biz_collect").format(amount=int(instance.profit()))
            self._buttons.append((rect, "collect", instance))
        text = ui_fonts.base(12, bold=True).render(label, True, text_color)
        surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _draw_upgrade_button(self, surface, rect, instance):
        maxed = not instance.can_upgrade()
        mouse_pos = pygame.mouse.get_pos()
        if maxed:
            pygame.draw.rect(surface, DISABLED, rect, border_radius=8)
            label = translate("biz_max")
            color = MUTED
        else:
            affordable = self.state.cash() >= instance.upgrade_cost()
            hover = rect.collidepoint(mouse_pos)
            pygame.draw.rect(surface, CARD_HI if hover else CARD, rect, border_radius=8)
            pygame.draw.rect(surface, CASH if affordable else DANGER, rect, width=1, border_radius=8)
            label = translate("biz_upgrade").format(cost=instance.upgrade_cost())
            color = CASH if affordable else (240, 205, 205)
            self._buttons.append((rect, "upgrade", instance))
        text = ui_fonts.base(11, bold=True).render(label, True, color)
        surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))


def _num(value):
    # Show 12.0 as "12" but 2.5 as "2.5".
    return f"{value:g}"


def _dim(color):
    return (color[0] // 2 + 20, color[1] // 2 + 20, color[2] // 2 + 20)


def _dark(color):
    return (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40))
