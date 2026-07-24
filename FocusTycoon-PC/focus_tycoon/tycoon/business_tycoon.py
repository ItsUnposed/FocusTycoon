"""The business tycoon: an electrical-engineering startup on the Tycoon page.

It owns its own simulation (machine cycles + study Wissen), state, view and HUD,
and exposes the same small interface as the city tycoon so the parent TycoonPanel
can switch to it with the main tab navbar. Inside, a second row of sub-tabs
switches between Machines, Study and Prototypes.
"""

from __future__ import annotations

import pygame

from ..i18n import translate
from ..util import ui_fonts
from .business_content import build_catalog, build_initial_state
from .business_model import CourseInstance, MachineInstance
from .business_simulation import (BusinessActions, BusinessBalance, ProgressSystem,
                                 StudySystem)
from .core import GameLoop
from .juice import JuiceEventBus
from .ui.business_hud import BusinessHud, HEIGHT as HUD_HEIGHT
from .ui.business_view import (BusinessView, SECTION_MACHINES, SECTION_PROTOTYPES,
                             SECTION_STUDY)

SUBTAB_HEIGHT = 40
SUBTAB_BG = (14, 15, 24)
SUBTAB_ACTIVE = (140, 220, 150)
SUBTAB_CARD = (34, 37, 52)
SUBTAB_CARD_HI = (46, 50, 68)
INK = (236, 238, 248)
BG = (12, 13, 22)

_SECTIONS = [
    (SECTION_MACHINES, "biz_tab_machines"),
    (SECTION_STUDY, "biz_tab_study"),
    (SECTION_PROTOTYPES, "biz_tab_prototypes"),
]


class BusinessTycoon:
    name = "business"
    title_key = "tycoon_tab_business"

    def __init__(self, gold, sound, saved_data):
        self._catalog = build_catalog()
        self.state = build_initial_state(gold)
        if saved_data is not None:
            self._load_data(saved_data)

        self._bus = JuiceEventBus()
        actions = BusinessActions()
        progress_system = ProgressSystem()
        study_system = StudySystem()

        def tick(elapsed_seconds):
            progress_system.tick(elapsed_seconds, self.state, self._bus)
            study_system.tick(elapsed_seconds, self.state, self._bus)

        self._game_loop = GameLoop(BusinessBalance.TICK_RATE_HZ, tick)
        self._hud = BusinessHud(self.state, self._catalog)
        self._view = BusinessView(self.state, actions, self._bus, sound, self._catalog)
        self._subtab_rects = []
        self._game_loop.start()

    # ---------- frame ----------

    def update(self, elapsed_seconds):
        pass  # the bars follow the state; no separate animation to advance

    def render(self, surface, rect):
        hud_rect = pygame.Rect(rect.x, rect.y, rect.width, HUD_HEIGHT)
        subtab_rect = pygame.Rect(rect.x, rect.y + HUD_HEIGHT, rect.width, SUBTAB_HEIGHT)
        body = pygame.Rect(rect.x, subtab_rect.bottom, rect.width, rect.height - HUD_HEIGHT - SUBTAB_HEIGHT)

        surface.fill((16, 17, 27), body)
        self._hud.render(surface, hud_rect)
        self._draw_subtabs(surface, subtab_rect)
        self._view.render(surface, body)

    def _draw_subtabs(self, surface, rect):
        surface.fill(SUBTAB_BG, rect)
        surface.fill((40, 42, 60), (rect.x, rect.bottom - 1, rect.width, 1))
        self._subtab_rects = []
        x = rect.x + 16
        for section, key in _SECTIONS:
            label = translate(key)
            width = ui_fonts.base(13, bold=True).size(label)[0] + 30
            tab_rect = pygame.Rect(x, rect.y + 7, width, SUBTAB_HEIGHT - 14)
            active = self._view.section == section
            if active:
                color, text_color = SUBTAB_ACTIVE, BG
            elif tab_rect.collidepoint(pygame.mouse.get_pos()):
                color, text_color = SUBTAB_CARD_HI, INK
            else:
                color, text_color = SUBTAB_CARD, INK
            pygame.draw.rect(surface, color, tab_rect, border_radius=tab_rect.height // 2)
            text = ui_fonts.base(13, bold=True).render(label, True, text_color)
            surface.blit(text, (tab_rect.centerx - text.get_width() // 2, tab_rect.centery - text.get_height() // 2))
            self._subtab_rects.append((tab_rect, section))
            x += width + 8

    # ---------- input ----------

    def handle_click(self, position):
        for tab_rect, section in self._subtab_rects:
            if tab_rect.collidepoint(position):
                self._view.section = section
                return
        self._view.handle_click(position)

    def is_over_interactive(self, position):
        for tab_rect, _ in self._subtab_rects:
            if tab_rect.collidepoint(position):
                return True
        return self._view.is_over(position)

    # ---------- task reward / lifecycle ----------

    def on_task_reward(self, reward_gold):
        pass

    def shutdown(self):
        self._game_loop.stop()
        self._hud.stop()

    # ---------- persistence ----------

    def save_data(self):
        machines = []
        for instance in self.state.machines().values():
            machines.append({
                "id": instance.definition.id,
                "level": instance.level(),
                "progress": round(instance.progress(), 3),
                "ready": instance.is_ready(),
            })
        courses = []
        for instance in self.state.courses().values():
            courses.append({"id": instance.definition.id, "level": instance.level()})
        return {
            "machines": machines,
            "courses": courses,
            "prototypes": list(self.state.prototype_ids()),
            "bargeld": round(self.state.bargeld(), 2),
            "wissen": round(self.state.wissen(), 2),
        }

    def _load_data(self, data):
        bargeld = data.get("bargeld")
        wissen = data.get("wissen")
        self.state.restore(
            float(bargeld) if _is_number(bargeld) else 0.0,
            float(wissen) if _is_number(wissen) else 0.0)
        # Prototypes first, so prototype-gated machines can be restored.
        if isinstance(data.get("prototypes"), list):
            for prototype_id in data["prototypes"]:
                definition = self._catalog.prototype_by_id.get(str(prototype_id))
                if definition is not None:
                    self.state.develop_prototype(definition)
        if isinstance(data.get("machines"), list):
            for item in data["machines"]:
                if not isinstance(item, dict):
                    continue
                definition = self._catalog.machine_by_id.get(str(item.get("id", "")))
                if definition is None or self.state.owns_machine(definition.id):
                    continue
                instance = MachineInstance(definition)
                level = item.get("level")
                progress = item.get("progress")
                instance.restore(level if _is_int(level) else 1,
                                 float(progress) if _is_number(progress) else 0.0,
                                 item.get("ready") is True)
                self.state.add_machine(instance)
        if isinstance(data.get("courses"), list):
            for item in data["courses"]:
                if not isinstance(item, dict):
                    continue
                definition = self._catalog.course_by_id.get(str(item.get("id", "")))
                if definition is None or self.state.enrolled(definition.id):
                    continue
                instance = CourseInstance(definition)
                level = item.get("level")
                instance.restore(level if _is_int(level) else 1)
                self.state.add_course(instance)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
