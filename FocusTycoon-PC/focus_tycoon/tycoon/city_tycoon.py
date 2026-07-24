"""The city-builder tycoon: one selectable tycoon on the Tycoon page.

It owns its own simulation loop, state, view and HUD. The parent TycoonPanel
hosts one or more tycoons and switches between them with a tab navbar, so every
tycoon exposes the same small set of methods (update / render / handle_click /
is_over_interactive / on_task_reward / shutdown / save_data).
"""

from __future__ import annotations

import pygame

from .city_content import all_milestones, build_catalog, build_initial_city
from .city_model import BuildingInstance
from .city_simulation import (CityActions, CityBalance, CityMilestoneSystem,
                             IncomeSystem)
from .core import GameLoop
from .juice import JuiceEventBus, ParticleEffectRequest, ParticleStyle
from .ui.city_hud import CityHud, HEIGHT as HUD_HEIGHT
from .ui.city_view import CityView, MAP_HEIGHT, MAP_WIDTH
from .ui.particle_layer import ParticleLayer
from .ui.screen_shaker import ScreenShaker

# How tall the bottom build bar is (native pixels).
BUILD_BAR_HEIGHT = 80


class CityTycoon:
    # "name" is this tycoon's slot in the save file; "title_key" is its tab label.
    name = "city"
    title_key = "tycoon_tab_city"

    def __init__(self, gold, sound, saved_data):
        self._catalog = build_catalog()
        self.state = build_initial_city(gold)
        # Rebuild a saved city before the simulation starts touching the state.
        if saved_data is not None:
            self._load_data(saved_data)

        self._bus = JuiceEventBus()
        actions = CityActions()
        income_system = IncomeSystem()
        milestone_system = CityMilestoneSystem(all_milestones())

        # The particle layer is built with a tile size of 1, so a burst position
        # is taken as straight pixel coordinates on the map surface.
        self._particle_layer = ParticleLayer(1, MAP_WIDTH, MAP_HEIGHT)
        self._screen_shaker = ScreenShaker()

        # Runs on the GameLoop's background thread (see core.py), so it only
        # touches thread-safe state.
        def tick(elapsed_seconds):
            income_system.tick(elapsed_seconds, self.state, self._bus)
            milestone_system.tick(self.state, self._bus)

        self._game_loop = GameLoop(CityBalance.TICK_RATE_HZ, tick)
        self._hud = CityHud(self.state, self._catalog)
        self._view = CityView(self.state, actions, self._bus, self._particle_layer,
                              self._screen_shaker, sound, self._catalog)

        # The transform of the scaled map, so we can map clicks back to the map.
        self._map_scale = 1.0
        self._map_origin = (0, 0)
        self._build_bar_rect = pygame.Rect(0, 0, 0, 0)
        self._game_loop.start()

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        self._view.update(elapsed_seconds)

    def render(self, surface, rect):
        # HUD strip on top, build bar on the bottom, the city in between.
        hud_rect = pygame.Rect(rect.x, rect.y, rect.width, HUD_HEIGHT)
        self._build_bar_rect = pygame.Rect(rect.x, rect.bottom - BUILD_BAR_HEIGHT,
                                           rect.width, BUILD_BAR_HEIGHT)
        map_area = pygame.Rect(rect.x, rect.y + HUD_HEIGHT, rect.width,
                               rect.height - HUD_HEIGHT - BUILD_BAR_HEIGHT)

        scale = min(map_area.width / MAP_WIDTH, map_area.height / MAP_HEIGHT)
        target_width = int(MAP_WIDTH * scale)
        target_height = int(MAP_HEIGHT * scale)
        origin_x = map_area.x + (map_area.width - target_width) // 2
        origin_y = map_area.y + (map_area.height - target_height) // 2
        self._map_scale = scale
        self._map_origin = (origin_x, origin_y)

        map_position = self._to_map_coordinates(pygame.mouse.get_pos())
        if map_position is not None:
            self._view.set_hover(map_position[0], map_position[1])
        else:
            self._view.hovered_tile = None

        self._hud.render(surface, hud_rect)
        map_surface = self._view.render()
        scaled = pygame.transform.smoothscale(map_surface, (target_width, target_height))
        surface.blit(scaled, (origin_x, origin_y))
        self._view.draw_build_bar(surface, self._build_bar_rect)
        self._view.draw_tooltip(surface, pygame.mouse.get_pos())

    # ---------- input ----------

    def _to_map_coordinates(self, position):
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
        if self._view.handle_ui_click(position):
            return
        map_position = self._to_map_coordinates(position)
        if map_position is not None:
            self._view.handle_map_click(map_position[0], map_position[1])

    def is_over_interactive(self, position):
        if self._view.is_over_ui(position) or self._build_bar_rect.collidepoint(position):
            return True
        map_position = self._to_map_coordinates(position)
        if map_position is None:
            return False
        grid_x, grid_y = self._view.screen_to_grid(map_position[0], map_position[1])
        return self.state.in_bounds(grid_x, grid_y)

    # ---------- task reward / lifecycle ----------

    def on_task_reward(self, reward_gold):
        # Celebrate a finished task with a little confetti over the city.
        self._particle_layer.spawn_burst(ParticleEffectRequest(None, ParticleStyle.CONFETTI, 40))
        self._screen_shaker.shake(0.6, 0.25)

    def shutdown(self):
        self._game_loop.stop()
        self._view.stop()
        self._hud.stop()

    # ---------- persistence ----------

    def save_data(self):
        buildings = []
        for building in self.state.buildings():
            buildings.append({
                "id": building.definition.id,
                "x": building.grid_x,
                "y": building.grid_y,
                "level": building.level(),
            })
        return {
            "buildings": buildings,
            "coins": round(self.state.coins(), 2),
            "milestones": list(self.state.reached_milestone_ids()),
        }

    def _load_data(self, data):
        # Read defensively so an old or edited save can never crash the app.
        by_id = {definition.id: definition for definition in self._catalog}
        if isinstance(data.get("buildings"), list):
            for item in data["buildings"]:
                if not isinstance(item, dict):
                    continue
                definition = by_id.get(str(item.get("id", "")))
                if definition is None:
                    continue
                x, y = item.get("x"), item.get("y")
                if not _is_int(x) or not _is_int(y):
                    continue
                if not self.state.in_bounds(x, y) or not self.state.is_empty(x, y):
                    continue
                instance = BuildingInstance(definition, x, y)
                level = item.get("level")
                instance.restore_level(level if _is_int(level) else 1)
                self.state.place(instance)
        coins = data.get("coins")
        if _is_number(coins):
            self.state.set_coins(float(coins))
        if isinstance(data.get("milestones"), list):
            for milestone_id in data["milestones"]:
                self.state.mark_reached(str(milestone_id))


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
