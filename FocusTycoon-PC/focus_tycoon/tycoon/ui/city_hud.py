"""The slim status bar at the top of the city page.

It shows the two currencies - gold (earned from tasks, spent on building new
buildings) and coins (earned by the city, spent on upgrades) - plus the city's
population and the next building that will unlock.
"""

from __future__ import annotations

import pygame

from ...i18n import translate
from ...util import ui_fonts
from .city_view import localized_name

GOLD = (245, 205, 96)
COIN = (120, 214, 220)
INK = (236, 238, 248)
MUTED = (168, 172, 194)
GREEN = (130, 210, 150)

HEIGHT = 72


class CityHud:
    def __init__(self, state, catalog):
        self.state = state
        self.catalog = catalog

    def stop(self):
        pass

    def render(self, surface, rect):
        panel = surface.subsurface(rect)
        width, height = rect.width, rect.height

        # Background gradient, one pixel row at a time so it is not flat.
        for y in range(height):
            ratio = y / max(1, height)
            color = (int(20 + (14 - 20) * ratio), int(22 + (15 - 22) * ratio), int(38 + (26 - 38) * ratio))
            panel.fill(color, (0, y, width, 1))
        panel.fill((40, 42, 60), (0, height - 1, width, 1))

        # Gold (spent on building new buildings).
        gold_amount = max(0, round(self.state.gold().balance()))
        self._draw_currency(panel, 20, GOLD, self._number(gold_amount), translate("city_gold_label"))

        # Coins (spent on upgrades), with the current income rate underneath.
        coins_amount = int(self.state.coins())
        income = self.state.total_income_per_second()
        self._draw_currency(panel, 240, COIN, self._number(coins_amount),
                            translate("city_coins_label").format(rate=f"{income:g}"))

        # Population.
        population = self.state.total_population()
        stats_x = 470
        panel.blit(ui_fonts.base(22, bold=True).render(str(population), True, INK), (stats_x, 16))
        panel.blit(ui_fonts.base(11).render(translate("city_residents_label"), True, MUTED), (stats_x, 44))

        # Next goal on the right: the nearest building still locked.
        next_goal = self._next_goal(population)
        if next_goal is not None:
            definition, needed = next_goal
            headline = translate("city_next").format(name=localized_name(definition))
            detail = translate("city_next_at").format(count=needed)
        else:
            headline = translate("city_all_unlocked")
            detail = translate("city_grow_free")
        headline_surface = ui_fonts.base(13, bold=True).render(headline, True, INK)
        detail_surface = ui_fonts.base(11).render(detail, True, MUTED)
        panel.blit(headline_surface, (width - headline_surface.get_width() - 24, 16))
        panel.blit(detail_surface, (width - detail_surface.get_width() - 24, 40))

    def _draw_currency(self, panel, x, color, amount_text, label):
        # A little coin, the amount, and a small label beneath.
        pygame.draw.circle(panel, (0, 0, 0), (x + 14, 34), 13)
        pygame.draw.circle(panel, color, (x + 13, 33), 13)
        pygame.draw.circle(panel, (0, 0, 0), (x + 13, 33), 13, 2)
        panel.blit(ui_fonts.base(22, bold=True).render(amount_text, True, color), (x + 36, 12))
        panel.blit(ui_fonts.base(11).render(label, True, MUTED), (x + 36, 42))

    def _number(self, value):
        # German number style uses '.' as the thousands separator.
        return f"{value:,}".replace(",", ".")

    def _next_goal(self, population):
        """The still-locked building with the lowest unlock population, if any."""
        best = None
        for definition in self.catalog:
            if definition.unlock_population > population:
                if best is None or definition.unlock_population < best.unlock_population:
                    best = definition
        if best is None:
            return None
        return best, best.unlock_population
