"""The top-down map of floating islands (for pygame).

- Click a producer's disc to CHEER it (spend gold; the fuel ring fills and drains).
- Click the button under a producer to UPGRADE it (costs resources).
- Click a locked island to unlock it (costs gold).

All click areas come from the same helpers as the drawing, so what you see is what
you click. The map is drawn into one fixed surface; the app scales it into its area
and converts mouse clicks back into map coordinates.
"""

from __future__ import annotations

import math
import random
import threading

import pygame

from ...util import ui_fonts
from ..juice import (GeneratorFueled, GeneratorUpgraded, MilestoneReached,
                     RecipeCompleted, ResourceProduced, SectorUnlocked)

TILE_SIZE = 72
GRID_COLUMNS = 17
GRID_ROWS = 11
MAP_WIDTH = GRID_COLUMNS * TILE_SIZE
MAP_HEIGHT = GRID_ROWS * TILE_SIZE

DISC_RADIUS = 27
DISC_Y_LIFT = 6
BUTTON_WIDTH = 122
BUTTON_HEIGHT = 22

SKY_TOP = (16, 17, 33)
SKY_BOTTOM = (33, 27, 54)
INK = (236, 238, 248)
MUTED = (168, 172, 194)
GOLD = (245, 205, 96)


def clamp_channel(value):
    # Keep a single red/green/blue value inside the valid 0-255 range.
    if value < 0:
        return 0
    if value > 255:
        return 255
    return int(value)


def mix(color_a, color_b, ratio):
    # Blend two RGB colors together. ratio 0.0 gives color_a, ratio 1.0 gives color_b,
    # and anything in between gives a smooth step from one to the other.
    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0
    return (clamp_channel(color_a[0] + (color_b[0] - color_a[0]) * ratio),
            clamp_channel(color_a[1] + (color_b[1] - color_a[1]) * ratio),
            clamp_channel(color_a[2] + (color_b[2] - color_a[2]) * ratio))


def brighter(color, amount):
    # Move a color partway toward white, which reads as "lighter" or "glowing".
    return mix(color, (255, 255, 255), amount)


def format_cost(cost):
    parts = []
    for resource, amount in cost.items():
        parts.append(f"{math.ceil(amount)}{resource.glyph}")
    return "  ".join(parts)


class FloatText:
    """A rising "+N" / text popup above a producer."""

    def __init__(self, x, y, vy, age, life, text, color, font_size):
        self.x = x
        self.y = y
        self.vy = vy
        self.age = age
        self.life = life
        self.text = text
        self.color = color
        self.font_size = font_size


class MapView:
    def __init__(self, state, fueling_service, bus, particle_layer, screen_shaker):
        self.state = state
        self.fueling_service = fueling_service
        self.bus = bus
        self.particle_layer = particle_layer
        self.screen_shaker = screen_shaker
        bus.subscribe(self.on_juice_event)

        # convert() matches the surface's pixel format to the display, which makes
        # pygame's blit (copy) operations noticeably faster later on.
        self.surface = pygame.Surface((MAP_WIDTH, MAP_HEIGHT)).convert()
        self.clock = 0.0
        self._floats = []
        self._floats_lock = threading.Lock()
        self._pulse_clock = {}  # generator_id -> clock time of the last pop
        self._pulse_lock = threading.Lock()

        # A stable star field: seeded with a fixed number so the stars land in the same
        # spots every time the game runs, instead of jumping around on each restart.
        random_generator = random.Random(20260708)
        self._stars = []
        for _ in range(190):
            self._stars.append((random_generator.randint(0, MAP_WIDTH - 1), random_generator.randint(0, MAP_HEIGHT - 1),
                                0.2 + random_generator.random() * 0.8))

    # ---------- lifecycle ----------

    def stop(self):
        pass  # no own timer needed (the app drives update / render)

    def update(self, dt_seconds):
        self.clock += dt_seconds
        self.particle_layer.update(dt_seconds)
        with self._floats_lock:
            for float_text in self._floats:
                float_text.age += dt_seconds
                # Move the floating text upward, then let a small constant "gravity"
                # slow that upward motion so it arcs and settles like a real popup.
                float_text.y += float_text.vy * dt_seconds
                float_text.vy += 26 * dt_seconds
            # Drop any floating text whose lifetime has run out.
            self._floats = [f for f in self._floats if f.age < f.life]

    # ---------- juice -> popups ----------

    def on_juice_event(self, event):
        if isinstance(event, GeneratorFueled):
            px, py = self._pixel_of(event.position)
            self._add_float(px, py - DISC_RADIUS - 18, "Cheered!", GOLD, 15)
            self._set_pulse(event.generator_id)
        elif isinstance(event, ResourceProduced):
            # Cap how many floating texts can be on screen at once, so a burst of
            # production events cannot flood the map with overlapping popups.
            with self._floats_lock:
                too_many = len(self._floats) > 60
            if too_many or event.amount < 1:
                return
            resource = event.resource
            px, py = self._pixel_of(event.position)
            self._add_float(px, py - DISC_RADIUS - 6,
                            f"+{round(event.amount)} {resource.glyph}", brighter(resource.accent, 0.35), 13)
        elif isinstance(event, RecipeCompleted):
            # Cap how many floating texts can be on screen at once, so a burst of
            # production events cannot flood the map with overlapping popups.
            with self._floats_lock:
                too_many = len(self._floats) > 60
            if too_many:
                return
            resource = event.recipe.output
            px, py = self._pixel_of(event.position)
            self._add_float(px, py - DISC_RADIUS - 6,
                            f"+{round(event.amount)} {resource.glyph}", brighter(resource.accent, 0.4), 15)
        elif isinstance(event, GeneratorUpgraded):
            px, py = self._pixel_of(event.position)
            self._add_float(px, py - DISC_RADIUS - 18, f"Level {event.new_level}!", (120, 230, 160), 18)
            self._set_pulse(event.generator_id)
        elif isinstance(event, SectorUnlocked):
            px, py = self._pixel_of(event.origin)
            self._add_float(px + TILE_SIZE, py + TILE_SIZE, "Island unlocked!", GOLD, 20)
        elif isinstance(event, MilestoneReached):
            self._add_float(MAP_WIDTH / 2.0, MAP_HEIGHT * 0.32,
                            "★ " + event.milestone.description, (255, 224, 150), 20)

    def _add_float(self, x, y, text, color, font_size):
        with self._floats_lock:
            self._floats.append(FloatText(x, y, -34, 0.0, 1.25, text, color, font_size))

    def _set_pulse(self, generator_id):
        with self._pulse_lock:
            self._pulse_clock[generator_id] = self.clock

    def _pixel_of(self, position):
        # No grid position means the event is not tied to one spot on the map,
        # so just center it on the map.
        if position is None:
            return MAP_WIDTH / 2.0, MAP_HEIGHT / 2.0
        # Convert a grid cell to the pixel position of its center, then lift it up a
        # little (DISC_Y_LIFT) so it lines up with where the producer disc is drawn.
        return (position.grid_x * TILE_SIZE + TILE_SIZE / 2.0,
                position.grid_y * TILE_SIZE + TILE_SIZE / 2.0 - DISC_Y_LIFT)

    # ---------- geometry (shared by paint + hit-test) ----------

    def _disc_center(self, generator):
        center_x = generator.position.grid_x * TILE_SIZE + TILE_SIZE / 2.0
        center_y = generator.position.grid_y * TILE_SIZE + TILE_SIZE / 2.0 - DISC_Y_LIFT
        return int(center_x), int(center_y)

    def _upgrade_button(self, generator):
        center_x, center_y = self._disc_center(generator)
        return pygame.Rect(int(center_x - BUTTON_WIDTH / 2.0),
                           int(center_y + DISC_RADIUS + 8), BUTTON_WIDTH, BUTTON_HEIGHT)

    def _island_rect(self, definition):
        return pygame.Rect(definition.origin.grid_x * TILE_SIZE, definition.origin.grid_y * TILE_SIZE,
                           definition.width * TILE_SIZE, definition.height * TILE_SIZE)

    # ---------- input ----------

    def is_over_interactive(self, px, py):
        """Whether the point (px, py) is over something clickable, used to swap the cursor."""
        for sector in self.state.sectors().values():
            if not sector.is_unlocked():
                if self._island_rect(sector.definition).collidepoint(px, py):
                    return True
                continue
            for generator in sector.generators():
                center_x, center_y = self._disc_center(generator)
                if (self._upgrade_button(generator).collidepoint(px, py)
                        or math.hypot(px - center_x, py - center_y) <= DISC_RADIUS):
                    return True
        return False

    def handle_click(self, px, py):
        """Work out what was clicked at (px, py) and trigger the matching action."""
        for sector in self.state.sectors().values():
            if not sector.is_unlocked():
                continue
            for generator in sector.generators():
                if self._upgrade_button(generator).collidepoint(px, py):
                    self.fueling_service.upgrade(self.state, generator, self.bus)
                    return
                center_x, center_y = self._disc_center(generator)
                if math.hypot(px - center_x, py - center_y) <= DISC_RADIUS:
                    self.fueling_service.ignite(self.state, generator, self.bus)
                    return
        # Locked islands last, so a producer wins a tie.
        for sector in self.state.sectors().values():
            if not sector.is_unlocked() and self._island_rect(sector.definition).collidepoint(px, py):
                self.fueling_service.unlock_sector(self.state, sector, self.bus)
                return

    def get_tooltip(self, px, py):
        for sector in self.state.sectors().values():
            if not sector.is_unlocked():
                continue
            for generator in sector.generators():
                center_x, center_y = self._disc_center(generator)
                if math.hypot(px - center_x, py - center_y) <= DISC_RADIUS:
                    cost = generator.definition.fuel_cost_gold
                    if cost <= 0:
                        return "Cheer for free"
                    return f"Cheer: {math.ceil(cost)} gold"
        return None

    # ---------- painting ----------

    def render(self):
        surface = self.surface
        self._paint_sky(surface)
        # Screen shake: islands / particles / floats on one layer, moved by dx / dy.
        dx, dy = self.screen_shaker.update(0.016)
        layer = pygame.Surface((MAP_WIDTH, MAP_HEIGHT), pygame.SRCALPHA)
        for sector in self.state.sectors().values():
            self._paint_island(layer, sector)
        self.particle_layer.paint(layer)
        self._paint_floats(layer)
        surface.blit(layer, (dx, dy))
        return surface

    def _paint_sky(self, surface):
        # Fill the background with a top-to-bottom gradient, one row at a time.
        for y in range(MAP_HEIGHT):
            ratio = y / MAP_HEIGHT
            surface.fill(mix(SKY_TOP, SKY_BOTTOM, ratio), (0, y, MAP_WIDTH, 1))
        # twinkle drifts smoothly between 0 and 1 over time, so the whole star field
        # pulses gently instead of staying static.
        twinkle = 0.5 + 0.5 * math.sin(self.clock * 1.5)
        for index, (star_x, star_y, magnitude) in enumerate(self._stars):
            # Spread stars across 5 groups (index % 5) so they do not all twinkle in
            # perfect unison, which would look mechanical instead of natural.
            brightness = magnitude * (0.6 + 0.4 * ((index % 5) / 4.0) * twinkle)
            alpha = round(min(1.0, brightness) * 200)
            size = 2 if magnitude > 0.75 else 1
            star = pygame.Surface((size, size), pygame.SRCALPHA)
            star.fill((220, 226, 255, alpha))
            surface.blit(star, (star_x, star_y))

    def _paint_floats(self, surface):
        with self._floats_lock:
            floats = list(self._floats)
        for float_text in floats:
            # As the text gets older it fades out, reaching full transparency at its life limit.
            fade = max(0.0, min(1.0, 1 - float_text.age / float_text.life))
            alpha = round(fade * 255)
            if alpha <= 0:
                continue
            font = ui_fonts.for_text(float_text.text, float_text.font_size, bold=True)
            shadow = font.render(float_text.text, True, (0, 0, 0))
            shadow.set_alpha(round(alpha * 0.55))
            core = font.render(float_text.text, True, float_text.color)
            core.set_alpha(alpha)
            rect = core.get_rect(midtop=(int(float_text.x), int(float_text.y)))
            surface.blit(shadow, (rect.x + 1, rect.y + 1))
            surface.blit(core, rect)

    def _paint_island(self, surface, sector):
        definition = sector.definition
        island_rect = self._island_rect(definition)
        padding = 8
        x, y = island_rect.x + padding, island_rect.y + padding
        width, height = island_rect.width - padding * 2, island_rect.height - padding * 2
        arc = 34
        accent = definition.accent

        # Floating shadow.
        shadow = pygame.Surface((max(1, width - 28), 30), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 70), shadow.get_rect())
        surface.blit(shadow, (x + 14, y + height - 6))

        if not sector.is_unlocked():
            self._paint_locked_island(surface, definition, x, y, width, height, arc)
            return

        # Body gradient, rounded.
        top_color = mix(accent, (26, 30, 40), 0.55)
        bottom_color = mix(accent, (10, 12, 20), 0.78)
        body = pygame.Surface((width, height), pygame.SRCALPHA)
        for yy in range(height):
            body.fill(mix(top_color, bottom_color, yy / max(1, height)), (0, yy, width, 1))
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=arc)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(body, (x, y))

        # Top highlight.
        highlight = pygame.Surface((width, height // 3), pygame.SRCALPHA)
        pygame.draw.rect(highlight, (255, 255, 255, 28), highlight.get_rect(), border_radius=arc)
        surface.blit(highlight, (x, y))

        # Accent border.
        pygame.draw.rect(surface, (accent[0], accent[1], accent[2]),
                         (x, y, width, height), width=2, border_radius=arc)

        # Header.
        self._draw_left(surface, definition.display_name, 15, INK, x + 16, y + 10, bold=True)
        self._draw_left(surface, definition.subtitle, 11, (230, 235, 245), x + 16, y + 30)

        for generator in sector.generators():
            self._paint_producer(surface, generator)

    def _paint_locked_island(self, surface, definition, x, y, width, height, arc):
        body = pygame.Surface((width, height), pygame.SRCALPHA)
        for yy in range(height):
            body.fill(mix((38, 40, 52), (24, 25, 34), yy / max(1, height)), (0, yy, width, 1))
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=arc)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(body, (x, y))
        pygame.draw.rect(surface, (96, 100, 120), (x, y, width, height), width=2, border_radius=arc)

        center_x = x + width // 2
        center_y = y + height // 2 - 6
        # Padlock drawn by hand.
        pygame.draw.arc(surface, (150, 155, 175), (center_x - 10, center_y - 22, 20, 22), 0, math.pi, 3)
        pygame.draw.rect(surface, (120, 125, 145), (center_x - 15, center_y - 8, 30, 22), border_radius=6)

        self._draw_centered(surface, definition.display_name, 14, MUTED, center_x, y + 20, bold=True)
        self._draw_centered(surface, f"Unlock: {int(definition.unlock_cost)} gold", 12, GOLD, center_x, center_y + 30)
        self._draw_centered(surface, "(click)", 10, (150, 155, 175), center_x, center_y + 47)

    def _paint_producer(self, surface, generator):
        center_x, center_y = self._disc_center(generator)
        accent = generator.definition.accent
        fueled = generator.is_fueled()
        fuel = generator.fuel_fraction()
        level = generator.level()
        pop = self._pop_factor(generator.instance_id)
        # The disc grows a little with each level, but the growth is capped so it
        # never gets huge. On top of that, "pop" briefly makes it swell right after
        # a cheer or upgrade, then shrink back to normal size.
        core_radius = DISC_RADIUS + min(level - 1, 5)
        disc_radius = round(core_radius * (1 + 0.22 * pop))

        # Expanding click ring (a satisfying "pop").
        if pop > 0.001:
            ring_expand = int(DISC_RADIUS + (1 - pop) * 28)
            alpha = int(pop * 170)
            ring = brighter(accent, 0.45)
            self._circle_outline(surface, (ring[0], ring[1], ring[2], alpha), center_x, center_y, ring_expand, 3)

        # Pedestal shadow.
        pedestal = pygame.Surface((DISC_RADIUS * 2 - 4, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(pedestal, (0, 0, 0, 90), pedestal.get_rect())
        surface.blit(pedestal, (center_x - DISC_RADIUS + 2, center_y + DISC_RADIUS - 10))

        # Name above.
        self._draw_centered(surface, generator.definition.display_name, 11, INK,
                            center_x, center_y - DISC_RADIUS - 18, bold=True)

        # OVERBOOST (purely cosmetic).
        if self._is_overboost(generator):
            self._draw_centered(surface, "OVERBOOST", 10, (255, 138, 61),
                                center_x, center_y - DISC_RADIUS - 32, bold=True)

        # Fuel ring track.
        ring_radius = DISC_RADIUS + 6
        self._circle_outline(surface, (255, 255, 255, 28), center_x, center_y, ring_radius, 5)
        # Fuel ring fill (clockwise from the top).
        if fuel > 0:
            ring_color = brighter(accent, 0.25)
            start = math.pi / 2 - 2 * math.pi * fuel
            stop = math.pi / 2
            rect = pygame.Rect(center_x - ring_radius, center_y - ring_radius, ring_radius * 2, ring_radius * 2)
            pygame.draw.arc(surface, ring_color, rect, start, stop, 5)

        # Gear teeth (more per level).
        self._paint_gear_teeth(surface, center_x, center_y, disc_radius, level, accent, fueled)

        # Core disc (radial gradient, scales briefly on a pop).
        glow = brighter(accent, 0.35) if fueled else mix(accent, (40, 42, 54), 0.7)
        edge = mix(accent, (20, 22, 30), 0.5) if fueled else (46, 48, 60)
        self._radial_disc(surface, center_x, center_y - 6, disc_radius, glow, edge)

        # Inner ring from level 3.
        if level >= 3:
            inner_radius = disc_radius - 7
            self._circle_outline(surface, (255, 255, 255, 70 if fueled else 40),
                                 center_x, center_y, inner_radius, 2)

        # Glyph.
        glyph_color = (255, 255, 255) if fueled else (210, 214, 230)
        self._draw_centered(surface, generator.definition.glyph, 24, glyph_color, center_x, center_y + 2)

        # Orbiting "workers" (more per level).
        self._paint_workers(surface, center_x, center_y, disc_radius, level, accent, fueled)

        # Level pip.
        self._draw_centered(surface, f"Lv {level}", 9, (255, 255, 255), center_x, center_y + disc_radius - 8, bold=True)

        self._paint_upgrade_button(surface, generator)

    def _paint_gear_teeth(self, surface, center_x, center_y, disc_radius, level, accent, fueled):
        # Higher-level producers get more gear teeth, so leveling up is visible at a glance.
        teeth = 8 + (level - 1) * 2
        # Only spin the gear while the producer is actually fueled (working).
        spin = self.clock * 0.6 if fueled else 0
        tooth_color = mix(accent, (18, 20, 28), 0.35)
        inner_radius = disc_radius - 1
        outer_radius = disc_radius + 4
        # Draw one short line per tooth, evenly spaced around the circle.
        for i in range(teeth):
            angle = spin + i * (2 * math.pi / teeth)
            x0 = center_x + int(math.cos(angle) * inner_radius)
            y0 = center_y + int(math.sin(angle) * inner_radius)
            x1 = center_x + int(math.cos(angle) * outer_radius)
            y1 = center_y + int(math.sin(angle) * outer_radius)
            pygame.draw.line(surface, tooth_color, (x0, y0), (x1, y1), 4)

    def _paint_workers(self, surface, center_x, center_y, disc_radius, level, accent, fueled):
        workers = min(level, 6)
        if workers <= 0:
            return
        # Workers orbit faster while the producer is fueled (busy working) and slower otherwise.
        spin = self.clock * 1.4 if fueled else self.clock * 0.2
        orbit = disc_radius - 9
        dot_color = brighter(accent, 0.55)
        for i in range(workers):
            angle = spin + i * (2 * math.pi / workers)
            worker_x = center_x + int(math.cos(angle) * orbit)
            worker_y = center_y + int(math.sin(angle) * orbit) - 4
            self._circle_alpha(surface, (0, 0, 0, 90), worker_x, worker_y + 1, 2)
            pygame.draw.circle(surface, dot_color, (worker_x, worker_y), 2)

    def _paint_upgrade_button(self, surface, generator):
        button = self._upgrade_button(generator)
        maxed = not generator.can_upgrade()
        cost = generator.upgrade_cost_at_current_level()
        affordable = (not maxed) and self.state.inventory().has_all(cost)

        if maxed:
            fill = (52, 54, 66)
            border = (90, 94, 110)
        elif affordable:
            fill = (46, 74, 58)
            border = (96, 200, 140)
        else:
            fill = (58, 46, 50)
            border = (150, 100, 108)
        pygame.draw.rect(surface, fill, button, border_radius=12)
        pygame.draw.rect(surface, border, button, width=1, border_radius=12)

        if maxed:
            text = "MAX LEVEL"
            color = MUTED
        else:
            text = f"Upgrade  {format_cost(cost)}"
            color = (210, 245, 220) if affordable else (240, 205, 205)
        self._draw_centered(surface, text, 11, color, button.centerx, button.centery)

    # ---------- small helpers ----------

    def _is_overboost(self, generator):
        return (not generator.can_upgrade()) and generator.fuel_fraction() >= 0.95

    def _pop_factor(self, instance_id):
        """How strong the "pop" animation should be right now, from 1.0 (just triggered)
        down to 0.0 (animation finished or never triggered)."""
        with self._pulse_lock:
            start_time = self._pulse_clock.get(instance_id)
        if start_time is None:
            return 0.0
        elapsed = self.clock - start_time
        duration = 0.35
        if elapsed < 0 or elapsed > duration:
            return 0.0
        return 1 - elapsed / duration

    def _draw_left(self, surface, text, size, color, x, y, bold=False):
        font = ui_fonts.for_text(text, size, bold=bold)
        surface.blit(font.render(text, True, color), (x, y))

    def _draw_centered(self, surface, text, size, color, center_x, baseline_y, bold=False):
        font = ui_fonts.for_text(text, size, bold=bold)
        rendered = font.render(text, True, color)
        surface.blit(rendered, rendered.get_rect(midbottom=(int(center_x), int(baseline_y + size * 0.28))))

    def _circle_outline(self, surface, rgba, center_x, center_y, radius, width):
        # A translucent color needs to be drawn onto its own transparent surface first
        # and then blended in, because pygame.draw.circle cannot blend partial
        # transparency directly onto a surface that has none of its own.
        if len(rgba) == 4 and rgba[3] < 255:
            temp = pygame.Surface((radius * 2 + width * 2, radius * 2 + width * 2), pygame.SRCALPHA)
            center = temp.get_rect().center
            pygame.draw.circle(temp, rgba, center, radius, width)
            surface.blit(temp, (center_x - center[0], center_y - center[1]))
        else:
            pygame.draw.circle(surface, rgba[:3], (center_x, center_y), radius, width)

    def _circle_alpha(self, surface, rgba, center_x, center_y, radius):
        temp = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(temp, rgba, temp.get_rect().center, radius)
        surface.blit(temp, (center_x - radius - 1, center_y - radius - 1))

    def _radial_disc(self, surface, center_x, center_y, radius, inner_color, outer_color):
        if radius <= 0:
            return
        temp = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        # pygame has no built-in radial gradient, so fake one by drawing solid circles
        # from the outer edge inward, each one slightly smaller and closer to inner_color.
        steps = max(1, radius)
        for i in range(steps, 0, -1):
            ratio = 1 - i / steps
            color = mix(inner_color, outer_color, ratio)
            pygame.draw.circle(temp, color, (radius, radius), i)
        surface.blit(temp, (center_x - radius, center_y - radius))
