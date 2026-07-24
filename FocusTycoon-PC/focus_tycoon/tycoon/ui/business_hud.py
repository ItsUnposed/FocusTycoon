"""The slim status bar at the top of the business page.

Shows the two currencies - gold (from tasks, spent buying businesses) and Cash
(earned by the businesses, spent on upgrades) - plus the next business to unlock.
"""

from __future__ import annotations

import pygame

from ...i18n import translate
from ...util import ui_fonts
from .business_view import localized_business_name

GOLD = (245, 205, 96)
CASH = (140, 220, 150)
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

        cash_amount = int(self.state.cash())
        rate = self.state.profit_per_second()
        self._draw_currency(panel, 240, CASH, self._number(cash_amount),
                            translate("biz_cash_label").format(rate=f"{rate:g}"))

        # Next business to unlock (by lifetime cash earned).
        next_goal = self._next_unlock()
        if next_goal is not None:
            definition = next_goal
            headline = translate("biz_next").format(name=localized_business_name(definition))
            detail = translate("biz_next_at").format(cash=int(definition.unlock_cash))
        else:
            headline = translate("biz_all_owned")
            detail = translate("biz_keep_growing")
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

    def _next_unlock(self):
        """The cheapest not-yet-owned, not-yet-unlocked business, if any."""
        best = None
        for definition in self.catalog:
            if self.state.owns(definition.id):
                continue
            if definition.unlock_cash <= self.state.lifetime_cash():
                continue
            if best is None or definition.unlock_cash < best.unlock_cash:
                best = definition
        return best
