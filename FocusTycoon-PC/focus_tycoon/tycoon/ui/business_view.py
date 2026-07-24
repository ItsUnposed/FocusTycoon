"""The business-tycoon view: the machines, study and prototypes sections.

All three sections are lists of cards drawn at native size. Which section is
shown is set by the parent BusinessTycoon (via the sub-tab bar). The view keeps a
list of clickable buttons that it rebuilds every frame for hit-testing.
"""

from __future__ import annotations

import pygame

from ...i18n import translate
from ...util import ui_fonts
from ..business_simulation import (CourseEnrolled, MachineBought, MachineCollected,
                                  MachineReady, PrototypeDeveloped)

SECTION_MACHINES = "machines"
SECTION_STUDY = "study"
SECTION_PROTOTYPES = "prototypes"

INK = (236, 238, 248)
MUTED = (168, 172, 194)
GOLD = (245, 205, 96)
BARGELD = (140, 220, 150)
WISSEN = (180, 160, 235)
CARD = (34, 37, 52)
CARD_HI = (46, 50, 68)
ACCENT = (122, 196, 255)
SUCCESS = (120, 214, 150)
DANGER = (226, 130, 130)
DISABLED = (58, 62, 82)
TRACK = (44, 48, 66)

CARD_HEIGHT = 80
CARD_GAP = 8


def _name(prefix, definition):
    key = prefix + definition.id
    text = translate(key)
    return definition.display_name if text == key else text


class BusinessView:
    def __init__(self, state, actions, bus, sound, catalog):
        self.state = state
        self.actions = actions
        self.bus = bus
        self.sound = sound
        self.catalog = catalog
        self.section = SECTION_MACHINES
        bus.subscribe(self.on_juice_event)
        self._buttons = []  # (rect, kind, payload)

    # ---------- sound feedback ----------

    def on_juice_event(self, event):
        if isinstance(event, MachineCollected):
            self.sound.play_note(659, 0.09, True)
        elif isinstance(event, MachineBought):
            self.sound.play_note(523, 0.10, False)
        elif isinstance(event, CourseEnrolled):
            self.sound.play_note(587, 0.10, False)
        elif isinstance(event, PrototypeDeveloped):
            self.sound.play_note(784, 0.16, True)
        elif isinstance(event, MachineReady):
            self.sound.play_note(440, 0.07, True)

    # ---------- input ----------

    def handle_click(self, position):
        for rect, kind, payload in self._buttons:
            if not rect.collidepoint(position):
                continue
            if kind == "collect_all":
                self.actions.collect_all(self.state, self.bus)
            elif kind in ("collect", "collect_body"):
                self.actions.collect_machine(self.state, payload, self.bus)
            elif kind == "upgrade_machine":
                self.actions.upgrade_machine(self.state, payload, self.bus)
            elif kind == "buy_machine":
                self.actions.buy_machine(self.state, payload, self.bus)
            elif kind == "enroll":
                self.actions.enroll_course(self.state, payload, self.bus)
            elif kind == "upgrade_course":
                self.actions.upgrade_course(self.state, payload, self.bus)
            elif kind == "develop":
                self.actions.develop_prototype(self.state, payload, self.bus)
            return

    def is_over(self, position):
        for rect, _, _ in self._buttons:
            if rect.collidepoint(position):
                return True
        return False

    # ---------- painting ----------

    def render(self, surface, rect):
        self._buttons = []
        if self.section == SECTION_STUDY:
            self._render_study(surface, rect)
        elif self.section == SECTION_PROTOTYPES:
            self._render_prototypes(surface, rect)
        else:
            self._render_machines(surface, rect)

    def _card_rects(self, rect, count, top_offset=0):
        x = rect.x + 16
        width = rect.width - 32
        y = rect.y + 10 + top_offset
        for _ in range(count):
            yield pygame.Rect(x, y, width, CARD_HEIGHT)
            y += CARD_HEIGHT + CARD_GAP

    def _swatch(self, surface, rect, accent, dim):
        color = _dim(accent) if dim else accent
        swatch = pygame.Rect(rect.x + 12, rect.y + 14, 52, 52)
        pygame.draw.rect(surface, color, swatch, border_radius=10)
        pygame.draw.rect(surface, _dark(color), swatch, width=1, border_radius=10)

    def _card_base(self, surface, rect, owned):
        pygame.draw.rect(surface, CARD if owned else (26, 28, 40), rect, border_radius=12)
        pygame.draw.rect(surface, (60, 64, 88), rect, width=1, border_radius=12)

    def _button(self, surface, rect, label, fill, border, text_color, size=12):
        pygame.draw.rect(surface, fill, rect, border_radius=8)
        if border is not None:
            pygame.draw.rect(surface, border, rect, width=1, border_radius=8)
        text = ui_fonts.base(size, bold=True).render(label, True, text_color)
        surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    # ---------- machines ----------

    def _render_machines(self, surface, rect):
        x = rect.x + 16
        width = rect.width - 32
        total_ready = sum(m.bargeld_per_cycle() * self.state.output_multiplier()
                          for m in self.state.machines().values() if m.is_ready())
        header = pygame.Rect(x, rect.y + 10, width, 34)
        self._draw_collect_all(surface, header, total_ready)

        for card_rect, definition in zip(self._card_rects(rect, len(self.catalog.machines), top_offset=44),
                                         self.catalog.machines):
            self._draw_machine_card(surface, card_rect, definition)

    def _draw_collect_all(self, surface, rect, total_ready):
        enabled = total_ready > 0
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if not enabled:
            fill, color = DISABLED, MUTED
            label = translate("biz_collect_all_idle")
        else:
            fill = (70, 150, 100) if hover else (54, 120, 82)
            color = (255, 255, 255)
            label = translate("biz_collect_all").format(amount=int(total_ready))
        self._button(surface, rect, label, fill, None, color, size=13)
        if enabled:
            self._buttons.append((rect, "collect_all", None))

    def _draw_machine_card(self, surface, rect, definition):
        instance = self.state.machine(definition.id)
        owned = instance is not None
        self._card_base(surface, rect, owned)
        self._swatch(surface, rect, definition.accent, dim=not owned)
        surface.blit(ui_fonts.base(15, bold=True).render(_name("machine_", definition), True,
                                                         INK if owned else MUTED), (rect.x + 76, rect.y + 12))

        if owned:
            info = translate("biz_machine_info").format(
                level=instance.level(), bargeld=int(instance.bargeld_per_cycle()), cycle=_num(definition.cycle_seconds))
            if definition.base_wissen > 0:
                info += translate("biz_machine_wissen_suffix").format(wissen=instance.wissen_per_cycle())
            surface.blit(ui_fonts.base(12).render(info, True, MUTED), (rect.x + 76, rect.y + 36))

            upgrade_rect = pygame.Rect(rect.right - 12 - 150, rect.y + 13, 150, 26)
            collect_rect = pygame.Rect(rect.right - 12 - 150, rect.y + 43, 150, 26)
            self._draw_upgrade_button(surface, upgrade_rect, instance.upgrade_cost(), instance.can_upgrade(),
                                      self.state.bargeld(), "upgrade_machine", instance)
            self._draw_collect_button(surface, collect_rect, instance)

            bar_left = rect.x + 76
            bar = pygame.Rect(bar_left, rect.y + 58, max(20, collect_rect.left - 14 - bar_left), 12)
            pygame.draw.rect(surface, TRACK, bar, border_radius=6)
            ready = instance.is_ready()
            fraction = 1.0 if ready else instance.progress()
            if fraction > 0:
                pygame.draw.rect(surface, SUCCESS if ready else ACCENT,
                                 pygame.Rect(bar.x, bar.y, max(6, int(bar.width * fraction)), bar.height),
                                 border_radius=6)
            if ready:
                ready_text = ui_fonts.base(11, bold=True).render(translate("biz_ready"), True, (18, 22, 30))
                surface.blit(ready_text, (bar.centerx - ready_text.get_width() // 2, bar.y - 1))
                self._buttons.append((rect, "collect_body", instance))
        else:
            locked = definition.unlock_prototype and not self.state.has_prototype(definition.unlock_prototype)
            info = translate("biz_machine_unowned").format(
                bargeld=definition.base_bargeld, cycle=_num(definition.cycle_seconds))
            if definition.base_wissen > 0:
                info += translate("biz_machine_wissen_suffix").format(wissen=definition.base_wissen)
            surface.blit(ui_fonts.base(12).render(info, True, MUTED), (rect.x + 76, rect.y + 36))
            action_rect = pygame.Rect(rect.right - 12 - 200, rect.centery - 17, 200, 34)
            if locked:
                proto = self.catalog.prototype_by_id.get(definition.unlock_prototype)
                label = translate("biz_needs_prototype").format(name=_name("prototype_", proto) if proto else "?")
                self._button(surface, action_rect, label, DISABLED, None, MUTED)
            else:
                self._draw_buy_button(surface, action_rect, definition.buy_cost_gold, "buy_machine", definition)

    # ---------- study ----------

    def _render_study(self, surface, rect):
        for card_rect, definition in zip(self._card_rects(rect, len(self.catalog.courses)),
                                        self.catalog.courses):
            self._draw_course_card(surface, card_rect, definition)

    def _draw_course_card(self, surface, rect, definition):
        instance = self.state.course(definition.id)
        enrolled = instance is not None
        self._card_base(surface, rect, enrolled)
        self._swatch(surface, rect, definition.accent, dim=not enrolled)
        surface.blit(ui_fonts.base(15, bold=True).render(_name("course_", definition), True,
                                                         INK if enrolled else MUTED), (rect.x + 76, rect.y + 14))

        action_rect = pygame.Rect(rect.right - 12 - 190, rect.centery - 17, 190, 34)
        if enrolled:
            info = translate("biz_course_info").format(level=instance.level(),
                                                       rate=f"{instance.wissen_per_second():g}")
            surface.blit(ui_fonts.base(12).render(info, True, WISSEN), (rect.x + 76, rect.y + 42))
            self._draw_upgrade_button(surface, action_rect, instance.upgrade_cost(), instance.can_upgrade(),
                                      self.state.bargeld(), "upgrade_course", instance, size=12)
        else:
            info = translate("biz_course_unowned").format(rate=f"{definition.base_wissen_per_second:g}")
            surface.blit(ui_fonts.base(12).render(info, True, MUTED), (rect.x + 76, rect.y + 42))
            self._draw_buy_button(surface, action_rect,
                                  definition.enroll_cost_gold, "enroll", definition,
                                  label=translate("biz_enroll").format(gold=int(definition.enroll_cost_gold)))

    # ---------- prototypes ----------

    def _render_prototypes(self, surface, rect):
        for card_rect, definition in zip(self._card_rects(rect, len(self.catalog.prototypes)),
                                        self.catalog.prototypes):
            self._draw_prototype_card(surface, card_rect, definition)

    def _draw_prototype_card(self, surface, rect, definition):
        developed = self.state.has_prototype(definition.id)
        self._card_base(surface, rect, developed)
        self._swatch(surface, rect, definition.accent, dim=not developed)
        surface.blit(ui_fonts.base(15, bold=True).render(_name("prototype_", definition), True, INK),
                     (rect.x + 76, rect.y + 12))
        surface.blit(ui_fonts.base(12).render(self._prototype_effect(definition), True, MUTED),
                     (rect.x + 76, rect.y + 38))

        action_rect = pygame.Rect(rect.right - 12 - 210, rect.centery - 17, 210, 34)
        if developed:
            self._button(surface, action_rect, translate("biz_developed"), (40, 66, 52), SUCCESS, SUCCESS)
        else:
            affordable = (self.state.wissen() >= definition.cost_wissen
                          and self.state.bargeld() >= definition.cost_bargeld)
            label = translate("biz_develop").format(wissen=definition.cost_wissen, bargeld=definition.cost_bargeld)
            fill = CARD_HI if action_rect.collidepoint(pygame.mouse.get_pos()) else CARD
            self._button(surface, action_rect, label, fill, WISSEN if affordable else DANGER,
                         WISSEN if affordable else (240, 205, 205), size=11)
            self._buttons.append((action_rect, "develop", definition))

    def _prototype_effect(self, definition):
        parts = []
        if definition.output_bonus > 0:
            parts.append(translate("biz_effect_output").format(percent=round(definition.output_bonus * 100)))
        if definition.unlock_machine:
            machine = self.catalog.machine_by_id.get(definition.unlock_machine)
            if machine is not None:
                parts.append(translate("biz_effect_unlock").format(name=_name("machine_", machine)))
        return "   ".join(parts)

    # ---------- shared buttons ----------

    def _draw_collect_button(self, surface, rect, instance):
        ready = instance.is_ready()
        amount = int(instance.bargeld_per_cycle() * self.state.output_multiplier())
        label = translate("biz_collect").format(amount=amount)
        if not ready:
            self._button(surface, rect, label, DISABLED, None, MUTED)
        else:
            hover = rect.collidepoint(pygame.mouse.get_pos())
            self._button(surface, rect, label, (70, 150, 100) if hover else (54, 120, 82), None, (255, 255, 255))
            self._buttons.append((rect, "collect", instance))

    def _draw_upgrade_button(self, surface, rect, cost, can_upgrade, have_bargeld, kind, payload, size=11):
        if not can_upgrade:
            self._button(surface, rect, translate("biz_max"), DISABLED, None, MUTED, size=size)
            return
        affordable = have_bargeld >= cost
        hover = rect.collidepoint(pygame.mouse.get_pos())
        self._button(surface, rect, translate("biz_upgrade").format(cost=cost),
                     CARD_HI if hover else CARD, BARGELD if affordable else DANGER,
                     BARGELD if affordable else (240, 205, 205), size=size)
        self._buttons.append((rect, kind, payload))

    def _draw_buy_button(self, surface, rect, cost_gold, kind, payload, label=None):
        affordable = self.state.gold().balance() >= cost_gold
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if label is None:
            label = translate("biz_buy").format(gold=int(cost_gold))
        self._button(surface, rect, label, CARD_HI if hover else (46, 66, 52),
                     SUCCESS if affordable else DANGER,
                     (210, 245, 220) if affordable else (240, 205, 205))
        self._buttons.append((rect, kind, payload))


def _num(value):
    return f"{value:g}"


def _dim(color):
    return (color[0] // 2 + 20, color[1] // 2 + 20, color[2] // 2 + 20)


def _dark(color):
    return (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40))
