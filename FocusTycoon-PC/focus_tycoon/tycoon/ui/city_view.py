"""The isometric city view (for pygame).

The city is a grid of tiles drawn in an isometric ("2.5D") style. Buildings are
little extruded blocks whose height grows with their number of floors, so the
skyline visibly grows as the city does.

- A build bar along the bottom lists every building you can place. Click one to
  select it, then click an empty tile to build it (costs gold).
- Click a building that is already there to upgrade it (costs coins).

The grid is drawn onto one fixed surface which the panel scales into place; the
build bar is drawn at native size by the panel so its text stays crisp.
"""

from __future__ import annotations

import math
import threading

import pygame

from ...util import ui_fonts
from ..city_simulation import (BuildingPlaced, BuildingSold, BuildingUpgraded,
                              CityMilestoneReached)
from ..juice import ParticleEffectRequest, ParticleStyle

# ---- isometric geometry ----
TILE_WIDTH = 64
TILE_HEIGHT = 32
HALF_WIDTH = TILE_WIDTH // 2
HALF_HEIGHT = TILE_HEIGHT // 2
# A building is drawn a little smaller than its tile, so there is a grass border.
BUILDING_HALF_WIDTH = HALF_WIDTH - 6
BUILDING_HALF_HEIGHT = HALF_HEIGHT - 3
FLOOR_HEIGHT = 14
BASE_HEIGHT = 10

# The fixed surface the city is drawn onto (the panel scales this to fit). Sized
# for the largest grid, with headroom above for tall buildings on the back row.
MAP_WIDTH = 700
MAP_HEIGHT = 560
ORIGIN_X = MAP_WIDTH // 2
ORIGIN_Y = 160

# ---- colours ----
SKY_TOP = (26, 28, 46)
SKY_BOTTOM = (46, 42, 68)
GRASS_A = (96, 160, 104)
GRASS_B = (86, 148, 96)
GRASS_EDGE = (66, 116, 78)
INK = (238, 240, 250)
MUTED = (170, 175, 196)
GOLD = (245, 205, 96)
CARD = (40, 44, 62)
CARD_HI = (54, 58, 80)
ACCENT = (122, 196, 255)
SUCCESS = (120, 214, 150)
DANGER = (226, 130, 130)
SELL = (240, 170, 80)
COIN = (120, 214, 220)
RESIDENT = (150, 210, 170)
WINDOW = (250, 240, 190)


def _clamp(value):
    if value < 0:
        return 0
    if value > 255:
        return 255
    return int(value)


def mix(color_a, color_b, ratio):
    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0
    return (_clamp(color_a[0] + (color_b[0] - color_a[0]) * ratio),
            _clamp(color_a[1] + (color_b[1] - color_a[1]) * ratio),
            _clamp(color_a[2] + (color_b[2] - color_a[2]) * ratio))


def darker(color, amount):
    # Move a colour partway toward black (used for the shaded side walls).
    return mix(color, (0, 0, 0), amount)


def brighter(color, amount):
    return mix(color, (255, 255, 255), amount)


class _PixelSpot:
    """A stand-in "position" whose grid coordinates are really pixels.

    The particle layer computes a burst origin as position.grid_x * tile_size.
    The city panel builds that layer with tile_size = 1, so passing pixels here
    lets the burst appear exactly where we want on the map surface.
    """

    def __init__(self, pixel_x, pixel_y):
        self.grid_x = pixel_x
        self.grid_y = pixel_y


class FloatText:
    """A short rising text popup ("+4 residents", "Lv 3", ...)."""

    def __init__(self, x, y, text, color, font_size):
        self.x = x
        self.y = y
        self.age = 0.0
        self.life = 1.3
        self.text = text
        self.color = color
        self.font_size = font_size


class CityView:
    def __init__(self, state, actions, bus, particle_layer, screen_shaker, sound, catalog):
        self.state = state
        self.actions = actions
        self.bus = bus
        self.particle_layer = particle_layer
        self.screen_shaker = screen_shaker
        # The sound sink (stays silent unless the player turned sound on).
        self.sound = sound
        # The list of buildable types (also the order shown in the build bar).
        self.catalog = catalog
        self._by_id = {definition.id: definition for definition in catalog}
        bus.subscribe(self.on_juice_event)

        self.surface = pygame.Surface((MAP_WIDTH, MAP_HEIGHT)).convert()
        self.clock = 0.0
        # The building type currently picked in the build bar (None = none).
        self.selected_definition = None
        # Sell mode: while on, clicking a building sells it for a partial refund.
        self.sell_mode = False
        # The "Sell" tool button in the build bar (its rect for hit-testing).
        self._sell_button_rect = pygame.Rect(0, 0, 0, 0)
        # The build bar can hold more buildings than fit, so it scrolls sideways.
        self._bar_scroll_x = 0.0
        self._bar_max_scroll = 0.0
        self._bar_region = pygame.Rect(0, 0, 0, 0)
        # The tile the mouse is hovering over in grid coordinates (or None).
        self.hovered_tile = None
        # A short-lived status message shown near the build bar.
        self.status = ""

        self._floats = []
        self._floats_lock = threading.Lock()
        # Button rectangles of the build bar, rebuilt every frame for hit-testing.
        self._bar_buttons = []

    # ---------- lifecycle ----------

    def stop(self):
        pass

    def update(self, dt_seconds):
        self.clock += dt_seconds
        self.particle_layer.update(dt_seconds)
        with self._floats_lock:
            for float_text in self._floats:
                float_text.age += dt_seconds
                float_text.y -= 26 * dt_seconds
            self._floats = [f for f in self._floats if f.age < f.life]

    # ---------- juice -> popups ----------

    def on_juice_event(self, event):
        if isinstance(event, BuildingPlaced):
            definition = self._by_id.get(event.building_id)
            text = self._effect_text(definition)
            self._add_float_at_tile(event.grid_x, event.grid_y, text, brighter(GRASS_A, 0.4))
            self._burst_at_tile(event.grid_x, event.grid_y, ParticleStyle.MAGIC_DUST, 20)
            self.screen_shaker.shake(0.4, 0.16)
            self.sound.play_note(523, 0.10, False)
        elif isinstance(event, BuildingUpgraded):
            self._add_float_at_tile(event.grid_x, event.grid_y, f"Lv {event.new_level}", (140, 230, 170))
            self._burst_at_tile(event.grid_x, event.grid_y, ParticleStyle.RUNE_RING, 24)
            self.screen_shaker.shake(0.5, 0.2)
            self.sound.play_note(659, 0.10, True)
        elif isinstance(event, BuildingSold):
            self._add_float_at_tile(event.grid_x, event.grid_y, f"+{event.refund_gold} gold", GOLD)
            self._burst_at_tile(event.grid_x, event.grid_y, ParticleStyle.SPARKLE, 16)
            self.sound.play_note(392, 0.10, False)
        elif isinstance(event, CityMilestoneReached):
            self._add_float(MAP_WIDTH / 2.0, MAP_HEIGHT * 0.3, event.milestone.description, GOLD, 16)
            self.particle_layer.spawn_burst(ParticleEffectRequest(None, ParticleStyle.CONFETTI, 60))
            self.screen_shaker.shake(1.0, 0.4)
            self.sound.play_note(784, 0.16, True)

    def _burst_at_tile(self, grid_x, grid_y, style, intensity):
        # The particle layer multiplies a position's grid coordinates by its
        # tile size to get pixels. The panel builds it with a tile size of 1, so
        # we can hand it the pixel spot straight through a small stand-in object.
        center_x, center_y = self._tile_center(grid_x, grid_y)
        self.particle_layer.spawn_burst(
            ParticleEffectRequest(_PixelSpot(center_x, center_y), style, intensity))

    def _effect_text(self, definition):
        if definition is None:
            return "Built"
        if definition.base_population > 0:
            return f"+{definition.base_population} residents"
        if definition.base_income_per_second > 0:
            return f"+{definition.base_income_per_second:g} coins/s"
        return "Built"

    def _add_float_at_tile(self, grid_x, grid_y, text, color):
        center_x, center_y = self._tile_center(grid_x, grid_y)
        self._add_float(center_x, center_y - 26, text, color, 13)

    def _add_float(self, x, y, text, color, font_size):
        with self._floats_lock:
            self._floats.append(FloatText(x, y, text, color, font_size))

    # ---------- geometry ----------

    def _tile_center(self, grid_x, grid_y):
        iso_x = (grid_x - grid_y) * HALF_WIDTH
        iso_y = (grid_x + grid_y) * HALF_HEIGHT
        return ORIGIN_X + iso_x, ORIGIN_Y + iso_y

    def screen_to_grid(self, map_x, map_y):
        """Turn a point on the (unscaled) map surface into a grid tile."""
        delta_x = map_x - ORIGIN_X
        delta_y = map_y - ORIGIN_Y
        # Invert the isometric projection (see _tile_center) and round to a tile.
        grid_x = round(delta_x / TILE_WIDTH + delta_y / TILE_HEIGHT)
        grid_y = round(delta_y / TILE_HEIGHT - delta_x / TILE_WIDTH)
        return grid_x, grid_y

    def _diamond(self, center_x, center_y, half_width, half_height, lift=0):
        top = (center_x, center_y - half_height - lift)
        right = (center_x + half_width, center_y - lift)
        bottom = (center_x, center_y + half_height - lift)
        left = (center_x - half_width, center_y - lift)
        return top, right, bottom, left

    # ---------- input ----------

    def set_hover(self, map_x, map_y):
        grid_x, grid_y = self.screen_to_grid(map_x, map_y)
        if self.state.in_bounds(grid_x, grid_y):
            self.hovered_tile = (grid_x, grid_y)
        else:
            self.hovered_tile = None

    def handle_map_click(self, map_x, map_y):
        grid_x, grid_y = self.screen_to_grid(map_x, map_y)
        if not self.state.in_bounds(grid_x, grid_y):
            return
        building = self.state.building_at(grid_x, grid_y)
        # Sell mode: clicking a building sells it for a partial gold refund.
        if self.sell_mode:
            if building is not None:
                self.actions.sell(self.state, building, self.bus)
            else:
                self.status = "Nothing to sell on this empty tile."
            return
        if building is not None:
            # A tile with a building: try to upgrade it.
            if not self.actions.upgrade(self.state, building, self.bus):
                if building.can_upgrade():
                    self.status = f"Not enough coins to upgrade ({int(building.upgrade_cost())})."
                else:
                    self.status = f"{building.definition.display_name} is at max level."
            return
        # An empty tile: build the selected type here (if one is picked).
        if self.selected_definition is None:
            self.status = "Pick a building from the bar below first."
            return
        self._try_build(self.selected_definition, grid_x, grid_y)

    def _try_build(self, definition, grid_x, grid_y):
        if definition.unlock_population > self.state.total_population():
            self.status = f"{definition.display_name} unlocks at {definition.unlock_population} residents."
            return
        if self.actions.build(self.state, definition, grid_x, grid_y, self.bus):
            self.status = ""
        else:
            self.status = f"Not enough gold ({int(definition.build_cost_gold)})."

    def handle_build_bar_click(self, position):
        # The sell tool is checked first.
        if self._sell_button_rect.collidepoint(position):
            self.sell_mode = not self.sell_mode
            # Selling and placing are different modes, so turn placing off.
            self.selected_definition = None
            return
        # Building buttons only count inside the scrolling region, so a button
        # scrolled partly out of view cannot be clicked through the edges.
        if not self._bar_region.collidepoint(position):
            return
        for button_rect, definition in self._bar_buttons:
            if button_rect.collidepoint(position):
                if definition.unlock_population > self.state.total_population():
                    self.status = (f"{definition.display_name} unlocks at "
                                   f"{definition.unlock_population} residents.")
                    return
                # Picking a building leaves sell mode.
                self.sell_mode = False
                # Clicking the already-selected building clears the selection.
                if self.selected_definition is definition:
                    self.selected_definition = None
                else:
                    self.selected_definition = definition
                return

    # ---------- painting: the map ----------

    def render(self):
        surface = self.surface
        self._paint_sky(surface)
        # Everything that can shake (ground, buildings, particles, popups) goes
        # on one layer that is nudged by the screen-shake offset.
        shake_x, shake_y = self.screen_shaker.update(0.016)
        layer = pygame.Surface((MAP_WIDTH, MAP_HEIGHT), pygame.SRCALPHA)
        self._paint_ground(layer)
        self._paint_buildings(layer)
        self.particle_layer.paint(layer)
        self._paint_floats(layer)
        surface.blit(layer, (shake_x, shake_y))
        return surface

    def _paint_sky(self, surface):
        for y in range(MAP_HEIGHT):
            ratio = y / MAP_HEIGHT
            surface.fill(mix(SKY_TOP, SKY_BOTTOM, ratio), (0, y, MAP_WIDTH, 1))

    def _paint_ground(self, layer):
        for grid_y in range(self.state.rows):
            for grid_x in range(self.state.columns):
                self._paint_tile(layer, grid_x, grid_y)

    def _paint_tile(self, layer, grid_x, grid_y):
        center_x, center_y = self._tile_center(grid_x, grid_y)
        # A checkerboard of two greens makes the grid easy to read.
        base = GRASS_A if (grid_x + grid_y) % 2 == 0 else GRASS_B
        points = self._diamond(center_x, center_y, HALF_WIDTH, HALF_HEIGHT)
        pygame.draw.polygon(layer, base, points)
        pygame.draw.polygon(layer, GRASS_EDGE, points, 1)

        # Highlight the hovered tile: green if the action here would work, red if not.
        if self.hovered_tile == (grid_x, grid_y):
            building = self.state.building_at(grid_x, grid_y)
            # In sell mode a building tile glows orange ("sellable"); empty is red.
            if self.sell_mode:
                pygame.draw.polygon(layer, SELL if building is not None else DANGER, points, 2)
                return
            if building is None:
                # Empty tile: green only if a building is picked and affordable.
                if self.selected_definition is not None:
                    affordable = self.state.gold().balance() >= self.selected_definition.build_cost_gold
                    unlocked = self.selected_definition.unlock_population <= self.state.total_population()
                    good = affordable and unlocked
                else:
                    good = False
            else:
                # A building: green only if it can be upgraded and we have the coins.
                good = building.can_upgrade() and self.state.coins() >= building.upgrade_cost()
            glow = SUCCESS if good else DANGER
            pygame.draw.polygon(layer, glow, points, 2)

    def _paint_buildings(self, layer):
        # Draw back-to-front so nearer buildings correctly overlap farther ones.
        buildings = self.state.buildings()
        buildings.sort(key=_depth_key)
        for building in buildings:
            self._paint_building(layer, building)

    def _paint_building(self, layer, building):
        definition = building.definition
        center_x, center_y = self._tile_center(building.grid_x, building.grid_y)

        # A park (0 floors) is just a raised green pad with a few trees.
        if definition.floors <= 0:
            pad = self._diamond(center_x, center_y, BUILDING_HALF_WIDTH, BUILDING_HALF_HEIGHT, lift=3)
            pygame.draw.polygon(layer, definition.roof_color, pad)
            pygame.draw.polygon(layer, darker(definition.roof_color, 0.3), pad, 1)
            for tree_x, tree_y in ((-6, 0), (6, -2), (0, 4)):
                pygame.draw.circle(layer, darker(GRASS_A, 0.1), (center_x + tree_x, center_y + tree_y - 6), 4)
            return

        height = BASE_HEIGHT + definition.floors * FLOOR_HEIGHT
        half_w, half_h = BUILDING_HALF_WIDTH, BUILDING_HALF_HEIGHT
        # Bottom diamond (sitting on the tile) and the raised top diamond.
        _, right, bottom, left = self._diamond(center_x, center_y, half_w, half_h)
        top_t, top_r, top_b, top_l = self._diamond(center_x, center_y, half_w, half_h, lift=height)

        wall = definition.wall_color
        left_face = [left, bottom, top_b, top_l]
        right_face = [bottom, right, top_r, top_b]
        pygame.draw.polygon(layer, darker(wall, 0.34), left_face)
        pygame.draw.polygon(layer, darker(wall, 0.14), right_face)
        # The roof (top diamond) is the brightest face.
        pygame.draw.polygon(layer, definition.roof_color, [top_t, top_r, top_b, top_l])
        pygame.draw.polygon(layer, darker(definition.roof_color, 0.25),
                            [top_t, top_r, top_b, top_l], 1)

        self._paint_windows(layer, center_x, center_y, definition.floors)

    def _paint_windows(self, layer, center_x, center_y, floors):
        # One little lit window per floor on each of the two visible walls.
        for floor in range(floors):
            lift = BASE_HEIGHT + floor * FLOOR_HEIGHT + FLOOR_HEIGHT // 2
            # Right wall window (to the lower-right of centre).
            right_x = center_x + BUILDING_HALF_WIDTH // 2
            right_y = center_y + BUILDING_HALF_HEIGHT // 2 - lift
            pygame.draw.rect(layer, WINDOW, (right_x - 1, right_y - 2, 3, 4))
            # Left wall window (to the lower-left of centre).
            left_x = center_x - BUILDING_HALF_WIDTH // 2
            left_y = center_y + BUILDING_HALF_HEIGHT // 2 - lift
            pygame.draw.rect(layer, darker(WINDOW, 0.25), (left_x - 1, left_y - 2, 3, 4))

    def _paint_floats(self, layer):
        with self._floats_lock:
            floats = list(self._floats)
        for float_text in floats:
            fade = max(0.0, 1.0 - float_text.age / float_text.life)
            color = mix(SKY_BOTTOM, float_text.color, fade)
            font = ui_fonts.base(float_text.font_size, bold=True)
            text_surface = font.render(float_text.text, True, color)
            layer.blit(text_surface, (int(float_text.x - text_surface.get_width() / 2), int(float_text.y)))

    # ---------- painting: the build bar (native size) ----------

    def draw_build_bar(self, surface, rect):
        """Draw the bottom build bar and remember each button for hit-testing.

        The Sell tool sits fixed on the left; the buildings fill a scrollable
        region to its right (use the mouse wheel over the bar to scroll).
        """
        pygame.draw.rect(surface, (24, 26, 40), rect)
        pygame.draw.rect(surface, (44, 46, 66), (rect.x, rect.y, rect.width, 1))

        mouse_pos = pygame.mouse.get_pos()
        population = self.state.total_population()
        gold = self.state.gold().balance()
        y = rect.y + 10
        button_height = rect.height - 32

        # The fixed Sell tool button on the far left.
        self._sell_button_rect = pygame.Rect(rect.x + 12, y, 78, button_height)
        self._draw_sell_button(surface, self._sell_button_rect, gold, mouse_pos)

        # The scrollable region that holds the building buttons.
        region = pygame.Rect(self._sell_button_rect.right + 10, rect.y,
                             rect.right - (self._sell_button_rect.right + 10) - 4, rect.height)
        self._bar_region = region

        button_width = 92
        gap = 6
        total_width = len(self.catalog) * (button_width + gap)
        self._bar_max_scroll = max(0.0, total_width - region.width)
        if self._bar_scroll_x > self._bar_max_scroll:
            self._bar_scroll_x = self._bar_max_scroll

        # Clip so buttons scrolled out of the region are not drawn over the rest.
        previous_clip = surface.get_clip()
        surface.set_clip(region)
        self._bar_buttons = []
        x = region.x - int(self._bar_scroll_x)
        for definition in self.catalog:
            button_rect = pygame.Rect(x, y, button_width, button_height)
            self._draw_bar_button(surface, button_rect, definition, population, gold, mouse_pos)
            self._bar_buttons.append((button_rect, definition))
            x += button_width + gap
        surface.set_clip(previous_clip)

        # A small status / hint line under everything.
        hint = self.status if self.status else self._default_hint()
        surface.blit(ui_fonts.base(12).render(hint, True, MUTED), (rect.x + 12, rect.bottom - 18))

    def scroll_build_bar(self, wheel_y):
        # Positive wheel scrolls left, negative scrolls right - like a track pad.
        self._bar_scroll_x = max(0.0, min(self._bar_max_scroll, self._bar_scroll_x - wheel_y * 60))

    # ---------- painting: the hover tooltip (native size) ----------

    def hovered_building(self):
        if self.hovered_tile is None:
            return None
        return self.state.building_at(self.hovered_tile[0], self.hovered_tile[1])

    def draw_tooltip(self, surface, mouse_pos):
        """Draw a small info box near the mouse for whatever it is hovering.

        Over a built tile it shows the building's output, level and upgrade cost;
        over an empty tile (with a building picked) it shows what that building
        would give. Drawn at native size so the text stays crisp.
        """
        if self.hovered_tile is None:
            return
        building = self.hovered_building()
        if building is not None:
            title, lines = self._tooltip_for_building(building)
        elif self.selected_definition is not None:
            title, lines = self._tooltip_for_definition(self.selected_definition)
        else:
            return
        self._draw_tooltip_box(surface, mouse_pos, title, lines)

    def _tooltip_for_building(self, building):
        definition = building.definition
        lines = [(f"Level {building.level()} / {definition.max_level}", MUTED)]
        if definition.base_population > 0:
            lines.append((f"{building.population()} residents", RESIDENT))
        if definition.base_income_per_second > 0:
            lines.append((f"+{building.income_per_second():g} coins/s", COIN))
        if building.can_upgrade():
            affordable = self.state.coins() >= building.upgrade_cost()
            lines.append((f"Upgrade: {building.upgrade_cost()} coins", COIN if affordable else DANGER))
        else:
            lines.append(("Max level", MUTED))
        if self.sell_mode:
            refund = int(definition.build_cost_gold * 0.75)
            lines.append((f"Sell: +{refund} gold", SELL))
        return definition.display_name, lines

    def _tooltip_for_definition(self, definition):
        locked = definition.unlock_population > self.state.total_population()
        lines = []
        if definition.base_population > 0:
            lines.append((f"{definition.base_population} residents", RESIDENT))
        if definition.base_income_per_second > 0:
            lines.append((f"+{definition.base_income_per_second:g} coins/s", COIN))
        if locked:
            lines.append((f"Locked until {definition.unlock_population} residents", DANGER))
        else:
            affordable = self.state.gold().balance() >= definition.build_cost_gold
            lines.append((f"Build: {int(definition.build_cost_gold)} gold", GOLD if affordable else DANGER))
        return definition.display_name, lines

    def _draw_tooltip_box(self, surface, mouse_pos, title, lines):
        title_font = ui_fonts.base(13, bold=True)
        line_font = ui_fonts.base(12)
        padding = 10
        line_height = 18
        # The box is as wide as its widest line of text.
        width = title_font.size(title)[0]
        for text, _ in lines:
            width = max(width, line_font.size(text)[0])
        box_width = width + padding * 2
        box_height = padding * 2 + line_height * (len(lines) + 1)

        # Place it just below-right of the cursor, but keep it on screen.
        x = mouse_pos[0] + 16
        y = mouse_pos[1] + 16
        if x + box_width > surface.get_width():
            x = mouse_pos[0] - box_width - 16
        if y + box_height > surface.get_height():
            y = surface.get_height() - box_height - 4
        box = pygame.Rect(x, y, box_width, box_height)
        pygame.draw.rect(surface, (22, 24, 38), box, border_radius=8)
        pygame.draw.rect(surface, (70, 74, 100), box, width=1, border_radius=8)

        text_y = y + padding
        surface.blit(title_font.render(title, True, INK), (x + padding, text_y))
        text_y += line_height + 2
        for text, color in lines:
            surface.blit(line_font.render(text, True, color), (x + padding, text_y))
            text_y += line_height

    def _draw_sell_button(self, surface, button_rect, gold, mouse_pos):
        if self.sell_mode:
            fill, border = mix(SELL, CARD, 0.35), SELL
        elif button_rect.collidepoint(mouse_pos):
            fill, border = CARD_HI, (86, 92, 120)
        else:
            fill, border = CARD, (60, 64, 88)
        pygame.draw.rect(surface, fill, button_rect, border_radius=8)
        pygame.draw.rect(surface, border, button_rect, width=1, border_radius=8)
        text_color = SELL if not self.sell_mode else INK
        surface.blit(ui_fonts.base(12, bold=True).render("Sell", True, text_color),
                     (button_rect.x + 12, button_rect.y + 8))
        surface.blit(ui_fonts.base(11).render("75% back", True, MUTED),
                     (button_rect.x + 10, button_rect.y + 26))

    def _default_hint(self):
        if self.sell_mode:
            return "Sell mode: click a building to sell it for 75% of its gold cost. Click Sell again to stop."
        if self.selected_definition is not None:
            return f"Selected: {self.selected_definition.display_name} - click an empty tile to build."
        return "Pick a building to build, or Sell to remove one. Click a built tile to upgrade it (coins)."

    def _draw_bar_button(self, surface, button_rect, definition, population, gold, mouse_pos):
        locked = definition.unlock_population > population
        selected = self.selected_definition is definition
        affordable = gold >= definition.build_cost_gold

        if selected:
            fill = mix(ACCENT, CARD, 0.4)
            border = ACCENT
        elif button_rect.collidepoint(mouse_pos) and not locked:
            fill = CARD_HI
            border = (86, 92, 120)
        else:
            fill = CARD
            border = (60, 64, 88)
        pygame.draw.rect(surface, fill, button_rect, border_radius=8)
        pygame.draw.rect(surface, border, button_rect, width=1, border_radius=8)

        # A tiny isometric icon of the building on the left of the button.
        self._draw_bar_icon(surface, button_rect.x + 20, button_rect.y + 26, definition, locked)

        name_color = MUTED if locked else INK
        surface.blit(ui_fonts.base(11, bold=True).render(definition.display_name, True, name_color),
                     (button_rect.x + 38, button_rect.y + 8))
        if locked:
            info = f"Locked - {definition.unlock_population} pop"
            info_color = MUTED
        else:
            info = f"{int(definition.build_cost_gold)} gold"
            info_color = GOLD if affordable else DANGER
        surface.blit(ui_fonts.base(11).render(info, True, info_color),
                     (button_rect.x + 38, button_rect.y + 24))

    def _draw_bar_icon(self, surface, center_x, center_y, definition, locked):
        # A small extruded block using the building's own colours, so each button
        # looks like the thing it builds.
        half_w, half_h = 12, 6
        height = 8 + min(definition.floors, 5) * 5
        wall = definition.wall_color if not locked else mix(definition.wall_color, (60, 62, 74), 0.6)
        roof = definition.roof_color if not locked else mix(definition.roof_color, (60, 62, 74), 0.6)
        bottom = (center_x, center_y + half_h)
        right = (center_x + half_w, center_y)
        left = (center_x - half_w, center_y)
        top_t = (center_x, center_y - half_h - height)
        top_r = (center_x + half_w, center_y - height)
        top_b = (center_x, center_y + half_h - height)
        top_l = (center_x - half_w, center_y - height)
        pygame.draw.polygon(surface, darker(wall, 0.34), [left, bottom, top_b, top_l])
        pygame.draw.polygon(surface, darker(wall, 0.14), [bottom, right, top_r, top_b])
        pygame.draw.polygon(surface, roof, [top_t, top_r, top_b, top_l])


def _depth_key(building):
    # Farther-back tiles have a smaller (x + y); drawing them first lets nearer
    # buildings paint on top.
    return building.grid_x + building.grid_y
