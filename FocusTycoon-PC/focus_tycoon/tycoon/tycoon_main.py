"""Hosts one or more tycoons on the Tycoon page and switches between them.

build_panel(gold_account, saved) builds the embeddable TycoonPanel. It owns the
shared sound and a list of tycoons (currently just the city), draws a small tab
navbar at the top to switch between them, and delegates the rest of the page to
whichever tycoon is active. Each tycoon keeps its own state and is saved
independently. The class is still named TycoonPanel and the factory build_panel,
so the rest of the app does not need to change.
"""

from __future__ import annotations

import pygame

from ..i18n import translate
from ..util import ui_fonts
from .business_tycoon import BusinessTycoon
from .city_tycoon import CityTycoon
from .ui.tone_player import TonePlayer

# The tab navbar at the top of the Tycoon page.
TAB_HEIGHT = 42
TAB_BG = (18, 20, 32)
TAB_ACTIVE = (122, 196, 255)
TAB_CARD = (40, 44, 62)
TAB_CARD_HI = (54, 58, 80)
INK = (236, 238, 248)
BG = (12, 13, 22)


class TycoonPanel:
    """The Tycoon page: a tab navbar plus the currently selected tycoon."""

    def __init__(self, gold, saved):
        self._tone_player = TonePlayer()
        saved_tycoons = saved.tycoons if saved is not None else {}

        # The list of tycoons, in tab order. More can be added here later.
        self._tycoons = [
            CityTycoon(gold, self._tone_player, saved_tycoons.get("city")),
            BusinessTycoon(gold, self._tone_player, saved_tycoons.get("business")),
        ]
        self._active = 0
        self._tab_rects = []

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        # Only the visible tycoon needs its view animated; the others still tick
        # their own simulation on their background threads.
        self._tycoons[self._active].update(elapsed_seconds)

    def render(self, surface, rect):
        tabs_rect = pygame.Rect(rect.x, rect.y, rect.width, TAB_HEIGHT)
        self._draw_tabs(surface, tabs_rect)
        body = pygame.Rect(rect.x, rect.y + TAB_HEIGHT, rect.width, rect.height - TAB_HEIGHT)
        self._tycoons[self._active].render(surface, body)

    def _draw_tabs(self, surface, rect):
        surface.fill(TAB_BG, rect)
        surface.fill((44, 46, 66), (rect.x, rect.bottom - 1, rect.width, 1))
        self._tab_rects = []
        x = rect.x + 16
        for index, tycoon in enumerate(self._tycoons):
            label = translate(tycoon.title_key)
            width = ui_fonts.base(14, bold=True).size(label)[0] + 36
            tab_rect = pygame.Rect(x, rect.y + 7, width, TAB_HEIGHT - 14)
            active = index == self._active
            if active:
                color, text_color = TAB_ACTIVE, BG
            elif tab_rect.collidepoint(pygame.mouse.get_pos()):
                color, text_color = TAB_CARD_HI, INK
            else:
                color, text_color = TAB_CARD, INK
            pygame.draw.rect(surface, color, tab_rect, border_radius=tab_rect.height // 2)
            text = ui_fonts.base(14, bold=True).render(label, True, text_color)
            surface.blit(text, (tab_rect.centerx - text.get_width() // 2,
                                tab_rect.centery - text.get_height() // 2))
            self._tab_rects.append(tab_rect)
            x += width + 8

    # ---------- input ----------

    def handle_click(self, position):
        for index, tab_rect in enumerate(self._tab_rects):
            if tab_rect.collidepoint(position):
                self._active = index
                return
        self._tycoons[self._active].handle_click(position)

    def is_over_interactive(self, position):
        for tab_rect in self._tab_rects:
            if tab_rect.collidepoint(position):
                return True
        return self._tycoons[self._active].is_over_interactive(position)

    def handle_scroll(self, wheel_y, position):
        self._tycoons[self._active].handle_scroll(wheel_y, position)

    # ---------- task reward ----------

    def trigger_focus_surge(self, reward_gold):
        # Reward the tycoon the player is currently looking at.
        self._tycoons[self._active].on_task_reward(reward_gold)

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
