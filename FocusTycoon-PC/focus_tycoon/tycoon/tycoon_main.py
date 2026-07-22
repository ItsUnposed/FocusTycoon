"""Wires the Tycoon engine together with the pygame view.

build_panel(gold_account, saved) builds an embeddable TycoonPanel: it owns the
whole Tycoon (state, simulation loop, map, HUD, juice) and the app renders it as
one page. When the window closes or resets, the app calls shutdown().
"""

from __future__ import annotations

from .content import GameContentRegistry, register_all, build_initial_state
from .core import GameLoop
from .juice import JuiceDirector, JuiceEventBus
from .simulation import BalancingConfig, MilestoneSystem, PlayerActionService, ProductionSystem
from .ui.hud_panel import HEIGHT as HUD_HEIGHT, HudPanel
from .ui.map_view import MAP_HEIGHT, MAP_WIDTH, TILE_SIZE, MapView
from .ui.particle_layer import ParticleLayer
from .ui.screen_shaker import ScreenShaker
from .ui.tone_player import TonePlayer

import pygame


class TycoonPanel:
    """The embedded Tycoon: state + simulation + map + HUD in one object."""

    def __init__(self, gold, saved):
        registry = GameContentRegistry()
        register_all(registry)
        self.state = build_initial_state(registry, gold)
        if saved is not None:
            saved.apply_tycoon(self.state)

        self._bus = JuiceEventBus()
        self._player_actions = PlayerActionService()
        production_system = ProductionSystem()
        milestone_system = MilestoneSystem(registry.all_milestones())

        self._particle_layer = ParticleLayer(TILE_SIZE, MAP_WIDTH, MAP_HEIGHT)
        self._tone_player = TonePlayer()
        self._screen_shaker = ScreenShaker()
        self._bus.subscribe(JuiceDirector(self._particle_layer, self._tone_player, self._screen_shaker))

        # This function is handed to GameLoop and runs on its background
        # thread (see core.py), separate from the pygame render loop, so it
        # must stay lightweight and only touch thread-safe state.
        def tick(elapsed_seconds):
            production_system.tick(elapsed_seconds, self.state, self._bus)
            milestone_system.tick(self.state, self._bus)

        self._game_loop = GameLoop(BalancingConfig.TICK_RATE_HZ, tick)

        self._hud_panel = HudPanel(self.state, self._bus)
        self._map_view = MapView(self.state, self._player_actions, self._bus,
                                 self._particle_layer, self._screen_shaker)

        # Transform of the scaled map (so we can map clicks back to map coordinates).
        self._map_scale = 1.0
        self._map_origin = (0, 0)

        self._game_loop.start()

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        self._map_view.update(elapsed_seconds)

    def render(self, surface, rect):
        # HUD strip on top, the map below it.
        hud_rect = pygame.Rect(rect.x, rect.y, rect.width, HUD_HEIGHT)
        self._hud_panel.render(surface, hud_rect)

        map_area = pygame.Rect(rect.x, rect.y + HUD_HEIGHT, rect.width, rect.height - HUD_HEIGHT)
        map_surface = self._map_view.render()

        # Fit the map into the area while keeping its aspect ratio.
        scale = min(map_area.width / MAP_WIDTH, map_area.height / MAP_HEIGHT)
        target_width = int(MAP_WIDTH * scale)
        target_height = int(MAP_HEIGHT * scale)
        origin_x = map_area.x + (map_area.width - target_width) // 2
        origin_y = map_area.y + (map_area.height - target_height) // 2
        self._map_scale = scale
        self._map_origin = (origin_x, origin_y)

        scaled = pygame.transform.smoothscale(map_surface, (target_width, target_height))
        surface.blit(scaled, (origin_x, origin_y))

    # ---------- input ----------

    def _to_map_coordinates(self, position):
        """Turn window coordinates into map coordinates (or None if outside)."""
        mouse_x, mouse_y = position
        origin_x, origin_y = self._map_origin
        if self._map_scale <= 0:
            return None
        local_x = (mouse_x - origin_x) / self._map_scale
        local_y = (mouse_y - origin_y) / self._map_scale
        if 0 <= local_x < MAP_WIDTH and 0 <= local_y < MAP_HEIGHT:
            return int(local_x), int(local_y)
        return None

    def handle_click(self, position):
        map_position = self._to_map_coordinates(position)
        if map_position is not None:
            self._map_view.handle_click(map_position[0], map_position[1])

    def is_over_interactive(self, position):
        map_position = self._to_map_coordinates(position)
        if map_position is None:
            return False
        return self._map_view.is_over_interactive(map_position[0], map_position[1])

    # ---------- focus surge ----------

    def trigger_focus_surge(self, reward_gold):
        """Speed up all production for a while as a reward for finishing a task.

        The bigger the task's gold reward, the longer the surge lasts (up to a
        cap). Called from the tasks page whenever a step is completed.
        """
        seconds = reward_gold * BalancingConfig.SURGE_SECONDS_PER_GOLD
        self.state.trigger_surge(seconds, BalancingConfig.SURGE_MAX_SECONDS)

    # ---------- sound ----------

    def is_sound_enabled(self):
        return self._tone_player.is_enabled()

    def toggle_sound(self):
        """Flip sound on/off and return the new state (True = on)."""
        new_state = not self._tone_player.is_enabled()
        self._tone_player.set_enabled(new_state)
        return new_state

    # ---------- lifecycle ----------

    def shutdown(self):
        self._game_loop.stop()
        self._tone_player.shutdown()
        self._map_view.stop()
        self._hud_panel.stop()


def build_panel(shared_gold, saved=None):
    return TycoonPanel(shared_gold, saved)
