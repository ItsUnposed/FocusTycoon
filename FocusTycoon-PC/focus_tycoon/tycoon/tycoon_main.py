"""Wires the city-builder engine together with the pygame view.

build_panel(gold_account, saved) builds an embeddable CityPanel: it owns the whole
city (state, simulation loop, view, HUD, feedback) and the app renders it as one
page. Finishing tasks feeds the shared gold account, which the city spends on
building. When the window closes or resets, the app calls shutdown().

The class is still named TycoonPanel and the factory build_panel, so the rest of
the app (which just embeds "the tycoon page") does not need to change.
"""

from __future__ import annotations

import pygame

from .city_content import build_catalog, all_milestones, build_initial_city
from .city_simulation import (CityActions, CityBalance, CityMilestoneSystem,
                             IncomeSystem)
from .core import GameLoop
from .juice import JuiceEventBus, ParticleEffectRequest, ParticleStyle
from .ui.city_hud import CityHud, HEIGHT as HUD_HEIGHT
from .ui.city_view import CityView, MAP_HEIGHT, MAP_WIDTH
from .ui.particle_layer import ParticleLayer
from .ui.screen_shaker import ScreenShaker
from .ui.tone_player import TonePlayer

# How tall the bottom build bar is (native pixels).
BUILD_BAR_HEIGHT = 80


class TycoonPanel:
    """The embedded city: state + simulation + view + HUD in one object."""

    def __init__(self, gold, saved):
        catalog = build_catalog()
        self.state = build_initial_city(gold)
        if saved is not None:
            saved.apply_city(self.state, catalog)

        self._bus = JuiceEventBus()
        actions = CityActions()
        income_system = IncomeSystem()
        milestone_system = CityMilestoneSystem(all_milestones())

        # The particle layer is built with a tile size of 1, so a burst position
        # is taken as straight pixel coordinates on the map surface.
        self._particle_layer = ParticleLayer(1, MAP_WIDTH, MAP_HEIGHT)
        self._tone_player = TonePlayer()
        self._screen_shaker = ScreenShaker()

        # This runs on the GameLoop's background thread (see core.py), separate
        # from the render loop, so it only touches thread-safe state.
        def tick(elapsed_seconds):
            income_system.tick(elapsed_seconds, self.state, self._bus)
            milestone_system.tick(self.state, self._bus)

        self._game_loop = GameLoop(CityBalance.TICK_RATE_HZ, tick)

        self._hud = CityHud(self.state, catalog)
        self._city_view = CityView(self.state, actions, self._bus, self._particle_layer,
                                   self._screen_shaker, self._tone_player, catalog)

        # The transform of the scaled map, so we can map clicks back to the map.
        self._map_scale = 1.0
        self._map_origin = (0, 0)
        self._build_bar_rect = pygame.Rect(0, 0, 0, 0)

        self._game_loop.start()

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        self._city_view.update(elapsed_seconds)

    def render(self, surface, rect):
        # HUD strip on top, build bar on the bottom, the city in between.
        hud_rect = pygame.Rect(rect.x, rect.y, rect.width, HUD_HEIGHT)
        self._build_bar_rect = pygame.Rect(rect.x, rect.bottom - BUILD_BAR_HEIGHT,
                                           rect.width, BUILD_BAR_HEIGHT)
        map_area = pygame.Rect(rect.x, rect.y + HUD_HEIGHT, rect.width,
                               rect.height - HUD_HEIGHT - BUILD_BAR_HEIGHT)

        # Work out how the map surface is scaled and placed inside the map area,
        # then use that to update which tile the mouse is hovering over.
        scale = min(map_area.width / MAP_WIDTH, map_area.height / MAP_HEIGHT)
        target_width = int(MAP_WIDTH * scale)
        target_height = int(MAP_HEIGHT * scale)
        origin_x = map_area.x + (map_area.width - target_width) // 2
        origin_y = map_area.y + (map_area.height - target_height) // 2
        self._map_scale = scale
        self._map_origin = (origin_x, origin_y)

        map_position = self._to_map_coordinates(pygame.mouse.get_pos())
        if map_position is not None:
            self._city_view.set_hover(map_position[0], map_position[1])
        else:
            self._city_view.hovered_tile = None

        # Draw the three parts.
        self._hud.render(surface, hud_rect)
        map_surface = self._city_view.render()
        scaled = pygame.transform.smoothscale(map_surface, (target_width, target_height))
        surface.blit(scaled, (origin_x, origin_y))
        self._city_view.draw_build_bar(surface, self._build_bar_rect)

    # ---------- input ----------

    def _to_map_coordinates(self, position):
        """Turn a window point into a point on the (unscaled) map surface, or None."""
        mouse_x, mouse_y = position
        origin_x, origin_y = self._map_origin
        if self._map_scale <= 0:
            return None
        local_x = (mouse_x - origin_x) / self._map_scale
        local_y = (mouse_y - origin_y) / self._map_scale
        if 0 <= local_x < MAP_WIDTH and 0 <= local_y < MAP_HEIGHT:
            return local_x, local_y
        return None

    def handle_click(self, position):
        # The build bar (native) is checked first, then the scaled map.
        if self._build_bar_rect.collidepoint(position):
            self._city_view.handle_build_bar_click(position)
            return
        map_position = self._to_map_coordinates(position)
        if map_position is not None:
            self._city_view.handle_map_click(map_position[0], map_position[1])

    def handle_scroll(self, wheel_y, position):
        # The mouse wheel scrolls the build bar sideways when the cursor is over it.
        if self._build_bar_rect.collidepoint(position):
            self._city_view.scroll_build_bar(wheel_y)

    def is_over_interactive(self, position):
        if self._build_bar_rect.collidepoint(position):
            return True
        map_position = self._to_map_coordinates(position)
        if map_position is None:
            return False
        grid_x, grid_y = self._city_view.screen_to_grid(map_position[0], map_position[1])
        return self.state.in_bounds(grid_x, grid_y)

    # ---------- task reward ----------

    def trigger_focus_surge(self, reward_gold):
        """Celebrate a finished task with a little confetti over the city.

        The gold reward itself is already added to the shared account by the
        tasks page; this is just the visual "well done" on the city side.
        """
        self._particle_layer.spawn_burst(ParticleEffectRequest(None, ParticleStyle.CONFETTI, 40))
        self._screen_shaker.shake(0.6, 0.25)

    # ---------- sound ----------

    def is_sound_enabled(self):
        return self._tone_player.is_enabled()

    def toggle_sound(self):
        new_state = not self._tone_player.is_enabled()
        self._tone_player.set_enabled(new_state)
        return new_state

    # ---------- lifecycle ----------

    def shutdown(self):
        self._game_loop.stop()
        self._tone_player.shutdown()
        self._city_view.stop()
        self._hud.stop()


def build_panel(shared_gold, saved=None):
    return TycoonPanel(shared_gold, saved)
