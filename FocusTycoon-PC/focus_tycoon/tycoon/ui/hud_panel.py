"""The slim status bar at the top of the Tycoon page.

It shows the gold balance (the scarce currency, so it stands out), a live row of
resource chips (glyph + amount per resource) and a status line for milestones and
unlocks.
"""

from __future__ import annotations

import math
import threading

import pygame

from ...util import ui_fonts
from ..juice import GeneratorUpgraded, MilestoneReached, SectorUnlocked

GOLD = (245, 205, 96)
INK = (236, 238, 248)
MUTED = (168, 172, 194)

HEIGHT = 84


class HudPanel:
    def __init__(self, state, bus):
        self.state = state
        self._status = "Cheer a producer to get started."
        self._status_lock = threading.Lock()
        bus.subscribe(self.on_juice_event)

    def stop(self):
        pass

    def on_juice_event(self, event):
        message = None
        if isinstance(event, MilestoneReached):
            message = "★ Milestone: " + event.milestone.description
        elif isinstance(event, SectorUnlocked):
            message = "New island unlocked!"
        elif isinstance(event, GeneratorUpgraded):
            message = f"Producer upgraded to level {event.new_level}."
        if message is not None:
            with self._status_lock:
                self._status = message

    def render(self, surface, rect):
        panel = surface.subsurface(rect)
        width, height = rect.width, rect.height

        # Background gradient.
        for y in range(height):
            ratio = y / max(1, height)
            color = (int(20 + (14 - 20) * ratio), int(22 + (15 - 22) * ratio), int(38 + (26 - 38) * ratio))
            panel.fill(color, (0, y, width, 1))
        panel.fill((40, 42, 60), (0, height - 1, width, 1))

        # Gold coin + amount.
        coin_x, coin_y = 20, 22
        pygame.draw.circle(panel, (0, 0, 0), (coin_x + 14, coin_y + 14), 13)
        pygame.draw.circle(panel, GOLD, (coin_x + 13, coin_y + 13), 13)
        pygame.draw.circle(panel, (180, 140, 40), (coin_x + 13, coin_y + 13), 13, 2)
        star = ui_fonts.for_text("✦", 15).render("✦", True, (120, 90, 20))
        panel.blit(star, (coin_x + 6, coin_y + 4))

        gold_amount = max(0, round(self.state.gold().balance()))
        gold_text = ui_fonts.base(24, bold=True).render(f"{gold_amount:,}".replace(",", "."), True, GOLD)
        panel.blit(gold_text, (coin_x + 36, coin_y - 2))
        panel.blit(ui_fonts.base(11).render("GOLD", True, MUTED), (coin_x + 36, coin_y + 24))

        # Resource chips.
        chip_x = coin_x + 150
        chip_y = 16
        max_x = width - 40
        for resource, amount in self.state.inventory().snapshot().items():
            if amount < 0.5:
                continue
            text = f"{resource.glyph} {math.floor(amount)}"
            font = ui_fonts.for_text(text, 13)
            chip_width = font.size(text)[0] + 20
            if chip_x + chip_width > max_x:
                break
            accent = resource.accent
            chip = pygame.Surface((chip_width, 26), pygame.SRCALPHA)
            pygame.draw.rect(chip, (accent[0], accent[1], accent[2], 40), chip.get_rect(), border_radius=13)
            pygame.draw.rect(chip, (accent[0], accent[1], accent[2], 170), chip.get_rect(),
                             width=1, border_radius=13)
            chip.blit(font.render(text, True, INK), (10, 4))
            panel.blit(chip, (chip_x, chip_y))
            chip_x += chip_width + 8

        # Status line.
        with self._status_lock:
            status = self._status
        status_font = ui_fonts.base(12, italic=True)
        panel.blit(status_font.render(status, True, (255, 216, 140)), (coin_x, height - 22))
