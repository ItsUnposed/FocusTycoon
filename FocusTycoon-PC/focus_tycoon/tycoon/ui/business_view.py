"""The business-tycoon view: the Education, Machines, Prototypes and Products
sections of the electrical-engineering startup.

All sections are lists of cards drawn at native size. Which section is shown is
set by the parent BusinessTycoon (via the sub-tab bar). The view rebuilds a list
of clickable buttons every frame for hit-testing.
"""

from __future__ import annotations

import pygame

from ...i18n import translate
from ...util import ui_fonts
from ..business_simulation import (AutomationBought, DegreeCompleted, DegreeStarted,
                                  GoldTraded, MachineBought, MachineBroke,
                                  MachineRepaired, ProductSold, PrototypeDeveloped,
                                  SkillLeveled)

SECTION_SKILLS = "skills"
SECTION_MACHINES = "machines"
SECTION_PROTOTYPES = "prototypes"
SECTION_PRODUCTS = "products"

INK = (236, 238, 248)
MUTED = (168, 172, 194)
GOLD = (245, 205, 96)
BARGELD = (140, 220, 150)
CARD = (34, 37, 52)
CARD_HI = (46, 50, 68)
ACCENT = (122, 196, 255)
SUCCESS = (120, 214, 150)
DANGER = (226, 130, 130)
BROKEN = (232, 120, 110)
DISABLED = (58, 62, 82)
TRACK = (44, 48, 66)

CARD_HEIGHT = 82
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
        self.section = SECTION_PRODUCTS
        bus.subscribe(self.on_juice_event)
        self._buttons = []  # (rect, kind, payload)
        # Some sections have more cards than fit, so the list scrolls (mouse
        # wheel, dragging the scrollbar thumb, or the keyboard).
        self._scroll_y = 0
        self._max_scroll = 0
        self._body_rect = pygame.Rect(0, 0, 0, 0)
        self._track_rect = pygame.Rect(0, 0, 0, 0)
        self._thumb_rect = pygame.Rect(0, 0, 0, 0)
        self._dragging = False
        self._drag_offset = 0

    # ---------- sound feedback ----------

    def on_juice_event(self, event):
        if isinstance(event, (ProductSold, GoldTraded)):
            self.sound.play_note(659, 0.09, True)
        elif isinstance(event, (MachineBought, PrototypeDeveloped, AutomationBought, DegreeStarted)):
            self.sound.play_note(523, 0.10, False)
        elif isinstance(event, (SkillLeveled, DegreeCompleted)):
            self.sound.play_note(784, 0.14, True)
        elif isinstance(event, MachineRepaired):
            self.sound.play_note(587, 0.10, False)
        elif isinstance(event, MachineBroke):
            self.sound.play_note(196, 0.16, False)

    # ---------- input ----------

    def handle_click(self, position):
        # Ignore clicks outside the scrolling body (buttons may be scrolled off).
        if not self._body_rect.collidepoint(position):
            return
        # Grabbing the scrollbar thumb starts a drag.
        if self._max_scroll > 0 and self._thumb_rect.collidepoint(position):
            self._dragging = True
            self._drag_offset = position[1] - self._thumb_rect.y
            return
        for rect, kind, payload in self._buttons:
            if not rect.collidepoint(position):
                continue
            self._run_action(kind, payload)
            return

    def scroll(self, delta):
        self._scroll_y = max(0, min(self._max_scroll, self._scroll_y + delta))

    def reset_scroll(self):
        self._scroll_y = 0
        self._dragging = False

    def handle_drag(self, position):
        if not self._dragging:
            return
        usable = self._track_rect.height - self._thumb_rect.height
        if usable <= 0:
            return
        relative = (position[1] - self._drag_offset) - self._track_rect.y
        fraction = max(0.0, min(1.0, relative / usable))
        self._scroll_y = int(fraction * self._max_scroll)

    def stop_drag(self):
        self._dragging = False

    def scroll_key(self, key):
        page = max(40, self._body_rect.height - 40)
        if key == pygame.K_UP:
            self.scroll(-40)
        elif key == pygame.K_DOWN:
            self.scroll(40)
        elif key == pygame.K_PAGEUP:
            self.scroll(-page)
        elif key == pygame.K_PAGEDOWN:
            self.scroll(page)

    def _run_action(self, kind, payload):
        if kind == "study_degree":
            self.actions.study_degree(self.state, payload, self.bus)
        elif kind == "level_skill":
            self.actions.level_skill(self.state, payload, self.bus)
        elif kind == "buy_machine":
            self.actions.buy_machine(self.state, payload, self.bus)
        elif kind == "upgrade_machine":
            self.actions.upgrade_machine(self.state, payload, self.bus)
        elif kind == "repair_machine":
            self.actions.repair_machine(self.state, payload, self.bus)
        elif kind == "develop":
            self.actions.develop_prototype(self.state, payload, self.bus)
        elif kind == "produce":
            self.actions.produce_product(self.state, payload, self.bus)
        elif kind == "sell":
            self.actions.sell_product(self.state, payload, self.bus)
        elif kind == "auto_produce":
            self.actions.buy_auto_produce(self.state, payload, self.bus)
        elif kind == "auto_sell":
            self.actions.buy_auto_sell(self.state, payload, self.bus)

    def is_over(self, position):
        for rect, _, _ in self._buttons:
            if rect.collidepoint(position):
                return True
        return False

    # ---------- painting ----------

    def render(self, surface, rect):
        self._buttons = []
        self._body_rect = rect
        entries = self._section_entries()
        content_height = 12 + len(entries) * (CARD_HEIGHT + CARD_GAP)
        self._max_scroll = max(0, content_height - rect.height)
        if self._scroll_y > self._max_scroll:
            self._scroll_y = self._max_scroll

        previous_clip = surface.get_clip()
        surface.set_clip(rect)
        x = rect.x + 16
        width = rect.width - 32
        y = rect.y + 12 - self._scroll_y
        for item, draw in entries:
            draw(surface, pygame.Rect(x, y, width, CARD_HEIGHT), item)
            y += CARD_HEIGHT + CARD_GAP
        surface.set_clip(previous_clip)
        self._draw_scrollbar(surface, rect)

    def _section_entries(self):
        if self.section == SECTION_SKILLS:
            return ([(d, self._draw_degree_card) for d in self.catalog.degrees]
                    + [(s, self._draw_skill_card) for s in self.catalog.skills])
        if self.section == SECTION_MACHINES:
            return [(m, self._draw_machine_card) for m in self.catalog.machines]
        if self.section == SECTION_PROTOTYPES:
            return [(p, self._draw_prototype_card) for p in self.catalog.prototypes]
        return [(p, self._draw_product_card) for p in self.catalog.products]

    def _draw_scrollbar(self, surface, rect):
        if self._max_scroll <= 0:
            self._track_rect = pygame.Rect(0, 0, 0, 0)
            self._thumb_rect = pygame.Rect(0, 0, 0, 0)
            return
        track = pygame.Rect(rect.right - 12, rect.y + 4, 8, rect.height - 8)
        self._track_rect = track
        pygame.draw.rect(surface, (44, 48, 66), track, border_radius=4)
        visible = rect.height / (rect.height + self._max_scroll)
        thumb_height = max(28, int(track.height * visible))
        thumb_y = track.y + int((track.height - thumb_height) * (self._scroll_y / self._max_scroll))
        self._thumb_rect = pygame.Rect(track.x, thumb_y, track.width, thumb_height)
        color = ACCENT if self._dragging else (100, 106, 132)
        pygame.draw.rect(surface, color, self._thumb_rect, border_radius=4)

    # ---------- shared drawing ----------

    def _card(self, surface, rect, active, accent):
        pygame.draw.rect(surface, CARD if active else (26, 28, 40), rect, border_radius=12)
        pygame.draw.rect(surface, (60, 64, 88), rect, width=1, border_radius=12)
        swatch = pygame.Rect(rect.x + 12, rect.y + 14, 52, 52)
        color = accent if active else _dim(accent)
        pygame.draw.rect(surface, color, swatch, border_radius=10)
        pygame.draw.rect(surface, _dark(color), swatch, width=1, border_radius=10)

    def _title(self, surface, rect, text, active):
        surface.blit(ui_fonts.base(15, bold=True).render(text, True, INK if active else MUTED),
                     (rect.x + 76, rect.y + 12))

    def _info(self, surface, rect, text, color=MUTED, y_offset=38):
        surface.blit(ui_fonts.base(12).render(text, True, color), (rect.x + 76, rect.y + y_offset))

    def _button(self, surface, rect, label, fill, border, text_color, kind=None, payload=None, size=11):
        pygame.draw.rect(surface, fill, rect, border_radius=8)
        if border is not None:
            pygame.draw.rect(surface, border, rect, width=1, border_radius=8)
        text = ui_fonts.base(size, bold=True).render(label, True, text_color)
        surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))
        if kind is not None:
            self._buttons.append((rect, kind, payload))

    def _action_button(self, surface, rect, label, kind, payload, affordable, size=11):
        hover = rect.collidepoint(pygame.mouse.get_pos())
        self._button(surface, rect, label, CARD_HI if hover else CARD,
                     BARGELD if affordable else DANGER,
                     BARGELD if affordable else (240, 205, 205), kind, payload, size)

    def _disabled_button(self, surface, rect, label, size=11):
        self._button(surface, rect, label, DISABLED, None, MUTED, size=size)

    # ---------- skills ----------

    def _draw_degree_card(self, surface, rect, definition):
        instance = self.state.degree(definition.id)
        self._card(surface, rect, True, definition.accent)
        self._title(surface, rect, _name("degree_", definition), True)
        self._info(surface, rect, translate("biz_degree_info"))
        action = pygame.Rect(rect.right - 12 - 230, rect.centery - 17, 230, 34)
        if instance.is_completed():
            self._button(surface, action, translate("biz_degree_done"), (40, 66, 52), SUCCESS, SUCCESS)
        elif instance.is_studying():
            bar = pygame.Rect(action.x, action.y + 4, action.width, 26)
            pygame.draw.rect(surface, TRACK, bar, border_radius=6)
            pygame.draw.rect(surface, ACCENT,
                             pygame.Rect(bar.x, bar.y, max(6, int(bar.width * instance.fraction())), bar.height),
                             border_radius=6)
            label = translate("biz_degree_studying").format(seconds=int(instance.remaining_seconds()) + 1)
            text = ui_fonts.base(11, bold=True).render(label, True, (18, 22, 30))
            surface.blit(text, (bar.centerx - text.get_width() // 2, bar.centery - text.get_height() // 2))
        elif definition.requires_degree and not self.state.has_degree(definition.requires_degree):
            required = self.catalog.degree_by_id.get(definition.requires_degree)
            self._disabled_button(surface, action, translate("biz_needs_degree").format(
                name=_name("degree_", required) if required else "?"))
        else:
            affordable = self.state.gold().balance() >= definition.cost_gold
            label = translate("biz_degree_study").format(
                gold=definition.cost_gold, seconds=int(definition.study_seconds))
            hover = action.collidepoint(pygame.mouse.get_pos())
            self._button(surface, action, label, CARD_HI if hover else CARD,
                         GOLD if affordable else DANGER, GOLD if affordable else (240, 205, 205),
                         "study_degree", instance)

    def _draw_skill_card(self, surface, rect, definition):
        instance = self.state.skill(definition.id)
        unlocked = self.state.skill_unlocked(definition)
        self._card(surface, rect, unlocked, definition.accent)
        self._title(surface, rect, _name("skill_", definition), unlocked)
        self._info(surface, rect, translate("biz_skill_level").format(
            level=instance.level(), max=definition.max_level))

        action = pygame.Rect(rect.right - 12 - 200, rect.centery - 17, 200, 34)
        if not unlocked:
            degree = self.catalog.degree_by_id.get(definition.unlock_degree)
            self._disabled_button(surface, action, translate("biz_needs_degree").format(
                name=_name("degree_", degree) if degree else "?"))
            return
        if instance.is_leveling():
            # A progress bar with the remaining time.
            bar = pygame.Rect(action.x, action.y + 4, action.width, 26)
            pygame.draw.rect(surface, TRACK, bar, border_radius=6)
            pygame.draw.rect(surface, ACCENT,
                             pygame.Rect(bar.x, bar.y, max(6, int(bar.width * instance.leveling_fraction())), bar.height),
                             border_radius=6)
            label = translate("biz_skill_leveling").format(seconds=int(instance.remaining_seconds()) + 1)
            text = ui_fonts.base(11, bold=True).render(label, True, (18, 22, 30))
            surface.blit(text, (bar.centerx - text.get_width() // 2, bar.centery - text.get_height() // 2))
        elif not instance.can_level():
            self._disabled_button(surface, action, translate("biz_max"))
        else:
            affordable = self.state.gold().balance() >= instance.cost_gold()
            seconds = int(instance.cooldown_seconds() * self.state.cooldown_multiplier())
            label = translate("biz_skill_up").format(gold=instance.cost_gold(), seconds=seconds)
            hover = action.collidepoint(pygame.mouse.get_pos())
            self._button(surface, action, label, CARD_HI if hover else CARD,
                         GOLD if affordable else DANGER, GOLD if affordable else (240, 205, 205),
                         "level_skill", instance)

    # ---------- machines ----------

    def _draw_machine_card(self, surface, rect, definition):
        instance = self.state.machine(definition.id)
        owned = instance is not None
        self._card(surface, rect, owned, definition.accent)
        self._title(surface, rect, _name("machine_", definition), owned)

        if owned:
            if instance.is_broken():
                self._info(surface, rect, translate("biz_machine_broken"), BROKEN)
            else:
                self._info(surface, rect, translate("biz_machine_level").format(level=instance.level()))
            if instance.is_broken():
                action = pygame.Rect(rect.right - 12 - 200, rect.centery - 17, 200, 34)
                affordable = self.state.bargeld() >= definition.repair_cost_bargeld
                self._action_button(surface, action, translate("biz_repair").format(
                    cost=int(definition.repair_cost_bargeld)), "repair_machine", instance, affordable, size=12)
            else:
                action = pygame.Rect(rect.right - 12 - 200, rect.centery - 17, 200, 34)
                if instance.can_upgrade():
                    affordable = self.state.bargeld() >= instance.upgrade_cost()
                    self._action_button(surface, action, translate("biz_upgrade").format(
                        cost=instance.upgrade_cost()), "upgrade_machine", instance, affordable, size=12)
                else:
                    self._disabled_button(surface, action, translate("biz_max"), size=12)
        else:
            met = self.state.meets_skill(definition.required_skill, definition.required_skill_level)
            self._info(surface, rect, translate("biz_machine_buy_info").format(
                bargeld=int(definition.buy_cost_bargeld)))
            action = pygame.Rect(rect.right - 12 - 220, rect.centery - 17, 220, 34)
            if not met:
                skill = self.catalog.skill_by_id.get(definition.required_skill)
                self._disabled_button(surface, action, translate("biz_needs_skill").format(
                    name=_name("skill_", skill) if skill else "?", level=definition.required_skill_level))
            else:
                affordable = self.state.bargeld() >= definition.buy_cost_bargeld
                self._action_button(surface, action, translate("biz_buy_bargeld").format(
                    cost=int(definition.buy_cost_bargeld)), "buy_machine", definition, affordable, size=12)

    # ---------- prototypes ----------

    def _draw_prototype_card(self, surface, rect, definition):
        developed = self.state.has_prototype(definition.id)
        self._card(surface, rect, developed, definition.accent)
        self._title(surface, rect, _name("prototype_", definition), True)
        product = self.catalog.product_by_id.get(definition.unlock_product)
        product_name = _name("product_", product) if product else "?"
        self._info(surface, rect, translate("biz_effect_unlock").format(name=product_name))

        action = pygame.Rect(rect.right - 12 - 230, rect.centery - 17, 230, 34)
        if developed:
            self._button(surface, action, translate("biz_developed"), (40, 66, 52), SUCCESS, SUCCESS)
            return
        met = self.state.meets_skill(definition.required_skill, definition.required_skill_level)
        if not met:
            skill = self.catalog.skill_by_id.get(definition.required_skill)
            self._disabled_button(surface, action, translate("biz_needs_skill").format(
                name=_name("skill_", skill) if skill else "?", level=definition.required_skill_level))
        else:
            affordable = self.state.bargeld() >= definition.cost_bargeld
            self._action_button(surface, action, translate("biz_develop").format(
                bargeld=int(definition.cost_bargeld)), "develop", definition, affordable)

    # ---------- products ----------

    def _draw_product_card(self, surface, rect, definition):
        prototype_id = self.catalog.product_prototype.get(definition.id)
        unlocked = prototype_id is not None and self.state.has_prototype(prototype_id)
        line = self.state.product_line(definition.id)
        self._card(surface, rect, unlocked, definition.accent)
        self._title(surface, rect, _name("product_", definition), unlocked)

        if not unlocked:
            proto = self.catalog.prototype_by_id.get(prototype_id) if prototype_id else None
            self._info(surface, rect, translate("biz_needs_prototype").format(
                name=_name("prototype_", proto) if proto else "?"))
            return

        # Material and price include the finance / marketing (BWL) bonuses.
        material = definition.material_cost_bargeld * self.state.material_multiplier()
        price = definition.sell_price_bargeld * self.state.sell_multiplier()
        info = translate("biz_product_info").format(
            material=int(round(material)), price=int(round(price)), stock=line.stock())
        self._info(surface, rect, info)

        # Production progress bar under the info line.
        bar = pygame.Rect(rect.x + 76, rect.y + 58, rect.width - 76 - 340, 12)
        pygame.draw.rect(surface, TRACK, bar, border_radius=6)
        if line.is_producing():
            pygame.draw.rect(surface, ACCENT,
                             pygame.Rect(bar.x, bar.y, max(6, int(bar.width * line.progress())), bar.height),
                             border_radius=6)

        # A 2x2 grid of buttons on the right: Produce / Sell / Auto-produce / Auto-sell.
        right = rect.right - 12
        col_w = 156
        pr = pygame.Rect(right - col_w * 2 - 6, rect.y + 13, col_w, 26)
        sr = pygame.Rect(right - col_w, rect.y + 13, col_w, 26)
        apr = pygame.Rect(right - col_w * 2 - 6, rect.y + 43, col_w, 26)
        asr = pygame.Rect(right - col_w, rect.y + 43, col_w, 26)

        machine = self.state.machine(definition.required_machine)
        can_produce = (machine is not None and not machine.is_broken() and not line.is_producing()
                       and self.state.bargeld() >= material)
        if machine is None:
            self._disabled_button(surface, pr, translate("biz_no_machine"))
        elif can_produce:
            self._action_button(surface, pr, translate("biz_produce"), "produce", definition, True)
        else:
            self._disabled_button(surface, pr, translate("biz_produce"))

        if line.stock() > 0:
            self._action_button(surface, sr, translate("biz_sell").format(
                amount=int(round(line.stock() * price))), "sell", definition, True)
        else:
            self._disabled_button(surface, sr, translate("biz_sell_empty"))

        self._auto_button(surface, apr, definition, line.auto_produce(), "auto_produce",
                          definition.auto_produce_cost, translate("biz_auto_produce"))
        self._auto_button(surface, asr, definition, line.auto_sell(), "auto_sell",
                          definition.auto_sell_cost, translate("biz_auto_sell"))

    def _auto_button(self, surface, rect, definition, on, kind, cost, label_on):
        if on:
            self._button(surface, rect, label_on, (40, 66, 52), SUCCESS, SUCCESS)
        elif not self.state.automation_unlocked():
            # Automations need the Business Basics (BWL) skill first.
            self._disabled_button(surface, rect, translate("biz_needs_bwl"))
        else:
            affordable = self.state.bargeld() >= cost
            self._action_button(surface, rect, translate("biz_automate").format(cost=int(cost)),
                                kind, definition, affordable)


def _dim(color):
    return (color[0] // 2 + 20, color[1] // 2 + 20, color[2] // 2 + 20)


def _dark(color):
    return (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40))
