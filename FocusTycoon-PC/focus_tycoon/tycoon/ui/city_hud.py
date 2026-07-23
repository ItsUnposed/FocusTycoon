"""The slim status bar at the top of the city page.

It shows the gold balance (spent on building), the city's population and passive
income, and the next thing to aim for (the next building that will unlock).
"""

from __future__ import annotations

import math

import pygame

from ...util import ui_fonts

GOLD = (245, 205, 96)
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

        # Gold coin + amount (the currency you spend on building).
        coin_x, coin_y = 20, 20
        pygame.draw.circle(panel, (0, 0, 0), (coin_x + 14, coin_y + 14), 13)
        pygame.draw.circle(panel, GOLD, (coin_x + 13, coin_y + 13), 13)
        pygame.draw.circle(panel, (180, 140, 40), (coin_x + 13, coin_y + 13), 13, 2)
        gold_amount = max(0, round(self.state.gold().balance()))
        # German number style uses '.' as the thousands separator.
        gold_text = ui_fonts.base(24, bold=True).render(f"{gold_amount:,}".replace(",", "."), True, GOLD)
        panel.blit(gold_text, (coin_x + 36, coin_y - 2))
        panel.blit(ui_fonts.base(11).render("GOLD", True, MUTED), (coin_x + 36, coin_y + 24))

        # Population and income read-outs.
        stats_x = coin_x + 200
        population = self.state.total_population()
        income = self.state.total_income_per_second()
        panel.blit(ui_fonts.base(20, bold=True).render(str(population), True, INK), (stats_x, coin_y - 2))
        panel.blit(ui_fonts.base(11).render("RESIDENTS", True, MUTED), (stats_x, coin_y + 24))

        income_x = stats_x + 120
        panel.blit(ui_fonts.base(20, bold=True).render(f"+{income:g}/s", True, GREEN), (income_x, coin_y - 2))
        panel.blit(ui_fonts.base(11).render("INCOME", True, MUTED), (income_x, coin_y + 24))

        # Next goal on the right: the nearest building still locked.
        next_goal = self._next_goal(population)
        if next_goal is not None:
            definition, needed = next_goal
            headline = f"Next: {definition.display_name}"
            detail = f"at {needed} residents"
        else:
            headline = "All buildings unlocked"
            detail = "Grow as big as you like"
        headline_surface = ui_fonts.base(13, bold=True).render(headline, True, INK)
        detail_surface = ui_fonts.base(11).render(detail, True, MUTED)
        panel.blit(headline_surface, (width - headline_surface.get_width() - 24, coin_y - 2))
        panel.blit(detail_surface, (width - detail_surface.get_width() - 24, coin_y + 22))

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
