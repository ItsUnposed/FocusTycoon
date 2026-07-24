"""The status bar at the top of the business page.

Shows Gold (from tasks - spent only on leveling skills) and Bargeld (the firm's
money, from selling products). On the right, a short reminder of the loop.
"""

from __future__ import annotations

import pygame

from ...i18n import translate
from ...util import ui_fonts

GOLD = (245, 205, 96)
BARGELD = (140, 220, 150)
INK = (236, 238, 248)
MUTED = (168, 172, 194)

HEIGHT = 72


class BusinessHud:
    def __init__(self, state, catalog):
        self.state = state
        self.catalog = catalog

    def stop(self):
        pass

    def render(self, surface, rect):
        panel = surface.subsurface(rect)
        width, height = rect.width, rect.height

        for y in range(height):
            ratio = y / max(1, height)
            color = (int(20 + (14 - 20) * ratio), int(22 + (15 - 22) * ratio), int(38 + (26 - 38) * ratio))
            panel.fill(color, (0, y, width, 1))
        panel.fill((40, 42, 60), (0, height - 1, width, 1))

        gold_amount = max(0, round(self.state.gold().balance()))
        self._draw_currency(panel, 20, GOLD, self._number(gold_amount), translate("biz_gold_label"))

        bargeld_amount = int(self.state.bargeld())
        self._draw_currency(panel, 260, BARGELD, self._number(bargeld_amount), translate("biz_bargeld_label"))

        headline = translate("biz_hud_headline")
        detail = translate("biz_hud_hint")
        headline_surface = ui_fonts.base(13, bold=True).render(headline, True, INK)
        detail_surface = ui_fonts.base(11).render(detail, True, MUTED)
        panel.blit(headline_surface, (width - headline_surface.get_width() - 24, 16))
        panel.blit(detail_surface, (width - detail_surface.get_width() - 24, 40))

    def _draw_currency(self, panel, x, color, amount_text, label):
        pygame.draw.circle(panel, (0, 0, 0), (x + 14, 34), 13)
        pygame.draw.circle(panel, color, (x + 13, 33), 13)
        pygame.draw.circle(panel, (0, 0, 0), (x + 13, 33), 13, 2)
        panel.blit(ui_fonts.base(22, bold=True).render(amount_text, True, color), (x + 36, 12))
        panel.blit(ui_fonts.base(11).render(label, True, MUTED), (x + 36, 42))

    def _number(self, value):
        return f"{value:,}".replace(",", ".")
