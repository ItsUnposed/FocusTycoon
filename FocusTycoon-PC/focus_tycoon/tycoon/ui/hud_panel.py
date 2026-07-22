"""The slim status bar at the top of the Tycoon page.

It shows the gold balance (the scarce currency, so it stands out), a live row of
resource chips (glyph + amount per resource), a Focus Surge meter (how long the
current task-driven speed-up still lasts) and a status line for milestones and
unlocks.
"""

from __future__ import annotations

import math
import threading

import pygame

from ...util import ui_fonts
from ..juice import GeneratorUpgraded, MilestoneReached, SectorUnlocked
from ..simulation import BalancingConfig

GOLD = (245, 205, 96)
INK = (236, 238, 248)
MUTED = (168, 172, 194)
# The Focus Surge meter uses a warm orange when it is running.
SURGE_ON = (255, 168, 84)

HEIGHT = 84
# Space reserved on the right of the panel for the Focus Surge meter.
SURGE_METER_WIDTH = 190


class HudPanel:
    def __init__(self, state, bus):
        self.state = state
        self._status = "Finish a task to power up your islands."
        self._status_lock = threading.Lock()
        # Listen for game events so the status line can react to them (see on_juice_event below).
        bus.subscribe(self.on_juice_event)

    def stop(self):
        pass  # the HUD has no timer or thread of its own to stop

    def on_juice_event(self, event):
        # Turn certain game events into a short status message shown at the bottom of the panel.
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

        # Background gradient: blend from one dark color at the top to another at the bottom,
        # one pixel row at a time, so the panel does not look flat.
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
        # Python's ',' thousands separator is swapped for '.' to match the German number style used in-game.
        gold_text = ui_fonts.base(24, bold=True).render(f"{gold_amount:,}".replace(",", "."), True, GOLD)
        panel.blit(gold_text, (coin_x + 36, coin_y - 2))
        panel.blit(ui_fonts.base(11).render("GOLD", True, MUTED), (coin_x + 36, coin_y + 24))

        # The surge meter sits on the right, so the resource chips must stop
        # before it to avoid drawing on top of each other.
        self._draw_surge_meter(panel, width, height)

        # Resource chips.
        chip_x = coin_x + 150
        chip_y = 16
        max_x = width - SURGE_METER_WIDTH - 40
        for resource, amount in self.state.inventory().snapshot().items():
            # Skip resources the player barely has; a chip showing "0" is not useful.
            if amount < 0.5:
                continue
            text = f"{resource.glyph} {math.floor(amount)}"
            font = ui_fonts.for_text(text, 13)
            chip_width = font.size(text)[0] + 20
            # Stop adding chips once we would run out of horizontal space in the panel.
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

    def _draw_surge_meter(self, panel, width, height):
        """Draw the Focus Surge meter: a bar that shows how long the current
        task-driven speed-up still has to run."""
        remaining = self.state.surge_seconds_remaining()
        # The bar fills up relative to the maximum surge the timer can hold.
        fraction = min(1.0, remaining / BalancingConfig.SURGE_MAX_SECONDS)

        meter_x = width - SURGE_METER_WIDTH - 20
        label = ui_fonts.base(11, bold=True).render("FOCUS SURGE", True, MUTED)
        panel.blit(label, (meter_x, 14))

        # Bar track.
        track = pygame.Rect(meter_x, 32, SURGE_METER_WIDTH, 12)
        pygame.draw.rect(panel, (44, 46, 62), track, border_radius=6)
        # Bar fill (only when there is some surge left).
        if fraction > 0:
            fill_width = max(6, int(SURGE_METER_WIDTH * fraction))
            fill = pygame.Rect(meter_x, 32, fill_width, 12)
            pygame.draw.rect(panel, SURGE_ON, fill, border_radius=6)

        # A short label under the bar: the time left, or a hint when idle.
        if remaining > 0:
            minutes = int(remaining) // 60
            seconds = int(remaining) % 60
            text = f"{minutes}:{seconds:02d} left"
            color = SURGE_ON
        else:
            text = "Idle - finish a task"
            color = MUTED
        panel.blit(ui_fonts.base(11).render(text, True, color), (meter_x, 50))
