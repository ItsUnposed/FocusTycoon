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
from ..business_simulation import (AutomationBought, AutomationToggled, DegreeCompleted,
                                  DegreeStarted, GoldTraded, MachineBought, MachineBroke,
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
ORANGE = (232, 158, 78)
DANGER = (226, 130, 130)
BROKEN = (232, 120, 110)
DISABLED = (58, 62, 82)
TRACK = (44, 48, 66)

CARD_HEIGHT = 82
CARD_GAP = 8
# A collapsible group header in the Education section is a bit shorter than a card.
GROUP_HEADER_HEIGHT = 54

# The themed groups the Education skills are sorted into, and their titles. The
# order here is the order the groups appear on screen.
_SKILL_GROUP_TITLES = {
    "basics": "biz_group_basics",
    "bachelor": "biz_group_bachelor",
    "master": "biz_group_master",
    "bwl": "biz_group_bwl",
}


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
        # Which Education groups are currently expanded (showing their skills).
        # The basics group starts open so the feature is easy to discover.
        self._expanded_groups = {"basics"}

    # ---------- sound feedback ----------

    def on_juice_event(self, event):
        if isinstance(event, (ProductSold, GoldTraded)):
            self.sound.play_note(659, 0.09, True)
        elif isinstance(event, (MachineBought, PrototypeDeveloped, AutomationBought, DegreeStarted)):
            self.sound.play_note(523, 0.10, False)
        elif isinstance(event, (SkillLeveled, DegreeCompleted)):
            self.sound.play_note(784, 0.14, True)
        elif isinstance(event, AutomationToggled):
            # A brighter note for switching on, a lower one for switching off.
            self.sound.play_note(659 if event.on else 330, 0.08, event.on)
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
        if kind == "toggle_group":
            self._toggle_group(payload)
            return
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
        elif kind == "toggle_auto_produce":
            self.actions.toggle_auto_produce(self.state, payload, self.bus)
        elif kind == "toggle_auto_sell":
            self.actions.toggle_auto_sell(self.state, payload, self.bus)

    def is_over(self, position):
        for rect, _, _ in self._buttons:
            if rect.collidepoint(position):
                return True
        return False

    # ---------- painting ----------

    def render(self, surface, rect):
        self._buttons = []
        self._body_rect = rect
        # Every row carries its own height, so a section can mix full cards with
        # shorter group headers (the Education section does this).
        rows = self._section_rows()
        content_height = 12
        for height, draw, item in rows:
            content_height += height + CARD_GAP
        self._max_scroll = max(0, content_height - rect.height)
        if self._scroll_y > self._max_scroll:
            self._scroll_y = self._max_scroll

        previous_clip = surface.get_clip()
        surface.set_clip(rect)
        x = rect.x + 16
        width = rect.width - 32
        y = rect.y + 12 - self._scroll_y
        for height, draw, item in rows:
            draw(surface, pygame.Rect(x, y, width, height), item)
            y += height + CARD_GAP
        surface.set_clip(previous_clip)
        self._draw_scrollbar(surface, rect)

    def _section_rows(self):
        # Each row is (height, draw_function, item). draw_function is called as
        # draw_function(surface, rect, item).
        if self.section == SECTION_SKILLS:
            return self._skill_rows()
        if self.section == SECTION_MACHINES:
            return [(CARD_HEIGHT, self._draw_machine_card, m) for m in self.catalog.machines]
        if self.section == SECTION_PROTOTYPES:
            return [(CARD_HEIGHT, self._draw_prototype_card, p) for p in self.catalog.prototypes]
        return [(CARD_HEIGHT, self._draw_product_card, p) for p in self.catalog.products]

    def _skill_rows(self):
        # The two degrees stay as their own cards at the very top.
        rows = []
        for degree in self.catalog.degrees:
            rows.append((CARD_HEIGHT, self._draw_degree_card, degree))
        # Then the skills, sorted into themed groups. Each group is a header row;
        # its skill cards only follow when the group is expanded.
        for group_id, skills in self._skill_groups():
            rows.append((GROUP_HEADER_HEIGHT, self._draw_group_header, group_id))
            if group_id in self._expanded_groups:
                for skill in skills:
                    rows.append((CARD_HEIGHT, self._draw_skill_card, skill))
        return rows

    def _skill_groups(self):
        # Build an ordered list of (group_id, [skills]) from the catalog, keeping
        # the order in which the groups first appear.
        order = []
        members = {}
        for skill in self.catalog.skills:
            if skill.group not in members:
                members[skill.group] = []
                order.append(skill.group)
            members[skill.group].append(skill)
        return [(group_id, members[group_id]) for group_id in order]

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

    def _toggle_group(self, group_id):
        # Clicking a group header opens it if closed, or closes it if open.
        if group_id in self._expanded_groups:
            self._expanded_groups.discard(group_id)
        else:
            self._expanded_groups.add(group_id)

    def _skills_in_group(self, group_id):
        result = []
        for skill in self.catalog.skills:
            if skill.group == group_id:
                result.append(skill)
        return result

    def _draw_group_header(self, surface, rect, group_id):
        # The whole rectangle is one big button that toggles the group, so draw
        # it like a card and light it up on hover.
        hover = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surface, CARD_HI if hover else CARD, rect, border_radius=12)
        pygame.draw.rect(surface, (60, 64, 88), rect, width=1, border_radius=12)

        # Title of the theme.
        title = translate(_SKILL_GROUP_TITLES.get(group_id, group_id))
        surface.blit(ui_fonts.base(15, bold=True).render(title, True, INK), (rect.x + 16, rect.y + 8))

        # A small summary: how many skills and the combined level of the group.
        skills = self._skills_in_group(group_id)
        total_level = 0
        max_level = 0
        for skill in skills:
            total_level += self.state.skill(skill.id).level()
            max_level += skill.max_level
        summary = translate("biz_group_summary").format(
            count=len(skills), level=total_level, max=max_level)
        surface.blit(ui_fonts.base(12).render(summary, True, MUTED), (rect.x + 16, rect.y + 30))

        # The little arrow: pointing down when closed (click to open downward),
        # pointing up when the group is already open.
        expanded = group_id in self._expanded_groups
        self._draw_chevron(surface, rect, expanded)

        # Register the whole header as the clickable toggle.
        self._buttons.append((rect, "toggle_group", group_id))

    def _draw_chevron(self, surface, rect, expanded):
        center_x = rect.right - 26
        center_y = rect.centery
        size = 7
        if expanded:
            # Arrow pointing up.
            points = [(center_x - size, center_y + size // 2),
                      (center_x + size, center_y + size // 2),
                      (center_x, center_y - size // 2 - 1)]
        else:
            # Arrow pointing down.
            points = [(center_x - size, center_y - size // 2),
                      (center_x + size, center_y - size // 2),
                      (center_x, center_y + size // 2 + 1)]
        pygame.draw.polygon(surface, INK, points)

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
                # Repairs cost Gold, so colour the button gold and check the gold balance.
                affordable = self.state.gold().balance() >= definition.repair_cost_gold
                hover = action.collidepoint(pygame.mouse.get_pos())
                self._button(surface, action, translate("biz_repair").format(
                    cost=int(definition.repair_cost_gold)), CARD_HI if hover else CARD,
                    GOLD if affordable else DANGER, GOLD if affordable else (240, 205, 205),
                    "repair_machine", instance, size=12)
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

        self._auto_button(surface, apr, definition, line, "produce")
        self._auto_button(surface, asr, definition, line, "sell")

    def _auto_button(self, surface, rect, definition, line, which):
        # "which" is "produce" or "sell"; pick that automation's data and labels.
        if which == "produce":
            bought = line.auto_produce_bought()
            active = line.auto_produce()
            cost = definition.auto_produce_cost
            buy_kind = "auto_produce"
            toggle_kind = "toggle_auto_produce"
            label_on = translate("biz_auto_produce")
            label_off = translate("biz_auto_produce_off")
        else:
            bought = line.auto_sell_bought()
            active = line.auto_sell()
            cost = definition.auto_sell_cost
            buy_kind = "auto_sell"
            toggle_kind = "toggle_auto_sell"
            label_on = translate("biz_auto_sell")
            label_off = translate("biz_auto_sell_off")

        if bought:
            # Already bought: a clickable on/off toggle (green when on, orange off).
            self._toggle_button(surface, rect, label_on if active else label_off,
                                toggle_kind, definition, active)
        elif not self.state.automation_unlocked():
            # Automations need the Business Basics (BWL) skill first.
            self._disabled_button(surface, rect, translate("biz_needs_bwl"))
        else:
            affordable = self.state.bargeld() >= cost
            self._action_button(surface, rect, translate("biz_automate").format(cost=int(cost)),
                                buy_kind, definition, affordable)

    def _toggle_button(self, surface, rect, label, kind, payload, on):
        # Green when the automation is on, orange when it is off. The whole button
        # stays clickable so the player can flip it back and forth.
        accent = SUCCESS if on else ORANGE
        base_fill = (40, 66, 52) if on else (66, 52, 34)
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            # Lighten the fill a little on hover for feedback.
            base_fill = (base_fill[0] + 12, base_fill[1] + 12, base_fill[2] + 12)
        self._button(surface, rect, label, base_fill, accent, accent, kind, payload)


def _dim(color):
    return (color[0] // 2 + 20, color[1] // 2 + 20, color[2] // 2 + 20)


def _dark(color):
    return (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40))
