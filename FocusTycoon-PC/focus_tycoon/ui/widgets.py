"""Small reusable pygame widgets for the interface.

Kept deliberately simple: a text field (single or multi line), a segmented choice,
a push button and a dropdown. Just enough for the two pages of the app.
"""

from __future__ import annotations

import pygame

from . import theme
from ..util import ui_fonts


class TextInput:
    """A text field. multiline=True turns it into a multi-line text area."""

    def __init__(self, rect, placeholder="", multiline=False, on_submit=None, mask=False):
        self.rect = rect
        self.placeholder = placeholder
        self.multiline = multiline
        self.on_submit = on_submit
        self.mask = mask  # True -> show the input as dots (password)
        self.text = ""
        self.focused = False
        self.enabled = True
        self._caret_visible = True
        self._caret_timer = 0.0

    def set_rect(self, rect):
        self.rect = rect

    def handle_event(self, event):
        if not self.enabled:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                if self.multiline:
                    self.text += "\n"
                elif self.on_submit is not None:
                    self.on_submit()
            elif event.key == pygame.K_TAB:
                pass  # do not put a tab into the field
            elif event.unicode and event.unicode.isprintable():
                self.text += event.unicode

    def update(self, delta_time):
        # The caret blinks once per second.
        self._caret_timer += delta_time
        if self._caret_timer >= 0.5:
            self._caret_timer = 0.0
            self._caret_visible = not self._caret_visible

    def draw(self, surface):
        # Highlight the border when the field is focused, so the player can see
        # where their typing will go.
        border_color = theme.ACCENT if self.focused else theme.STROKE
        theme.rounded_rect(surface, self.rect, theme.CARD, 8, border_color, 1)

        font = ui_fonts.base(14)
        # Leave a small gap between the box edge and the text/caret.
        inner_x = self.rect.x + 14
        inner_y = self.rect.y + 10

        if not self.text and not self.focused:
            surface.blit(font.render(self.placeholder, True, theme.MUTED), (inner_x, inner_y))
            return

        if self.multiline:
            self._draw_multiline(surface, font, inner_x, inner_y)
        else:
            self._draw_singleline(surface, font, inner_x, inner_y)

    def _draw_singleline(self, surface, font, x, y):
        text = ("•" * len(self.text)) if self.mask else self.text
        # Cut off on the left so the text never runs past the right edge.
        max_width = self.rect.width - 28
        while text and font.size(text)[0] > max_width:
            text = text[1:]
        surface.blit(font.render(text, True, theme.TEXT), (x, y))
        if self.focused and self._caret_visible:
            # Place the caret right after the visible text, so it looks like
            # the cursor is at the end of what the player typed.
            caret_x = x + font.size(text)[0] + 1
            pygame.draw.line(surface, theme.TEXT, (caret_x, y + 2),
                             (caret_x, y + font.get_height() - 2), 1)

    def _draw_multiline(self, surface, font, x, y):
        lines = self._wrap(font, self.rect.width - 28)
        line_height = font.get_height() + 2
        # Work out how many lines actually fit in the box, then only keep the
        # most recent ones - older lines simply scroll out of view above.
        max_lines = max(1, (self.rect.height - 16) // line_height)
        visible_lines = lines[-max_lines:]
        for index, line in enumerate(visible_lines):
            surface.blit(font.render(line, True, theme.TEXT), (x, y + index * line_height))
        if self.focused and self._caret_visible and visible_lines:
            last_line = visible_lines[-1]
            caret_x = x + font.size(last_line)[0] + 1
            caret_y = y + (len(visible_lines) - 1) * line_height
            pygame.draw.line(surface, theme.TEXT, (caret_x, caret_y + 2),
                             (caret_x, caret_y + font.get_height() - 2), 1)

    def _wrap(self, font, max_width):
        # Split the typed text into lines that are narrow enough to fit inside
        # the box, breaking on paragraph breaks ("\n") first and then on words.
        result = []
        for paragraph in self.text.split("\n"):
            if not paragraph:
                # An empty paragraph is a blank line - keep it as one.
                result.append("")
                continue
            current = ""
            for word in paragraph.split(" "):
                candidate = word if not current else current + " " + word
                if font.size(candidate)[0] <= max_width:
                    # The word still fits on the current line, keep building it.
                    current = candidate
                else:
                    # Adding this word would make the line too wide, so close
                    # off the current line and start a new one with this word.
                    if current:
                        result.append(current)
                    current = word
            result.append(current)
        return result


class SegmentedControl:
    """A segmented choice (for example Do-not-split / Fine / Medium / Coarse)."""

    def __init__(self, labels, selected_index, on_select=None):
        self.labels = labels
        self.selected_index = selected_index
        self.on_select = on_select
        self._segment_rects = []

    def set_labels(self, labels):
        self.labels = labels

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self._segment_rects):
                if rect.collidepoint(event.pos):
                    self.selected_index = index
                    if self.on_select is not None:
                        self.on_select(index)
                    break

    def draw(self, surface, x, y, height=40):
        font = ui_fonts.base(14, bold=True)
        padding = 6
        # Each segment is sized to fit its own label, with some extra room on
        # each side, so short and long labels both look comfortable.
        segment_widths = [font.size(label)[0] + 40 for label in self.labels]
        total_width = sum(segment_widths) + padding * (len(self.labels) + 1)
        container = pygame.Rect(x, y, total_width, height)
        theme.rounded_rect(surface, container, theme.CARD, 22, theme.STROKE, 1)

        self._segment_rects = []
        segment_x = x + padding
        for index, label in enumerate(self.labels):
            segment_rect = pygame.Rect(segment_x, y + padding, segment_widths[index], height - padding * 2)
            is_active = index == self.selected_index
            if is_active:
                theme.rounded_rect(surface, segment_rect, theme.ACCENT, segment_rect.height // 2)
            text_color = theme.BG if is_active else theme.TEXT
            theme.draw_text_centered(surface, label, 14, text_color,
                                     segment_rect.centerx, segment_rect.centery, bold=True)
            self._segment_rects.append(segment_rect)
            # Move the drawing position past this segment, ready for the next one.
            segment_x += segment_widths[index] + padding
        return container


class Button:
    """A simple pill button. It is drawn every frame; clicks go through handle_event."""

    def __init__(self, rect, text, background_color, text_color, on_click, enabled=True):
        self.rect = rect
        self.text = text
        self.background_color = background_color
        self.text_color = text_color
        self.on_click = on_click
        self.enabled = enabled

    def handle_event(self, event):
        if not self.enabled:
            return False
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos)):
            self.on_click()
            return True
        return False

    def draw(self, surface, mouse_pos):
        if not self.enabled:
            color = theme.DISABLED
        elif self.rect.collidepoint(mouse_pos):
            color = theme.brighter(self.background_color, 0.12)
        else:
            color = self.background_color
        theme.rounded_rect(surface, self.rect, color, self.rect.height // 2)
        if self.enabled:
            text_color = self.text_color
        else:
            text_color = theme.MUTED
        theme.draw_text_centered(surface, self.text, 13, text_color,
                                 self.rect.centerx, self.rect.centery, bold=True)


class Dropdown:
    """A small dropdown. options is a list of (value, label). Draw it last so its
    open list appears on top of everything else."""

    def __init__(self, rect, options, selected_index, on_select=None):
        self.rect = rect
        self.options = options
        self.selected_index = selected_index
        self.on_select = on_select
        self.is_open = False
        self._option_rects = []

    def selected_value(self):
        return self.options[self.selected_index][0]

    def handle_event(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        # Clicking the closed box itself just opens or closes the option list.
        if self.rect.collidepoint(event.pos):
            self.is_open = not self.is_open
            return True
        if self.is_open:
            for index, option_rect in enumerate(self._option_rects):
                if option_rect.collidepoint(event.pos):
                    self.selected_index = index
                    self.is_open = False
                    if self.on_select is not None:
                        self.on_select(index)
                    return True
            self.is_open = False  # a click anywhere else closes the list
        return False

    def draw(self, surface, mouse_pos):
        theme.rounded_rect(surface, self.rect, theme.CARD, 8, theme.STROKE, 1)
        label = self.options[self.selected_index][1]
        theme.draw_text(surface, label, 13, theme.TEXT, self.rect.x + 12, self.rect.y + 7, bold=True)
        theme.draw_text(surface, "▼", 11, theme.MUTED, self.rect.right - 20, self.rect.y + 9)

        self._option_rects = []
        if not self.is_open:
            return
        # Stack the option list directly below the closed box, one row per
        # option, each row the same height as the box itself.
        for index, option in enumerate(self.options):
            option_rect = pygame.Rect(self.rect.x, self.rect.bottom + 2 + index * self.rect.height,
                                      self.rect.width, self.rect.height)
            hovered = option_rect.collidepoint(mouse_pos)
            background = theme.CARD_HI if hovered else theme.CARD
            theme.rounded_rect(surface, option_rect, background, 8, theme.STROKE, 1)
            theme.draw_text(surface, option[1], 13, theme.TEXT,
                            option_rect.x + 12, option_rect.y + 7)
            self._option_rects.append(option_rect)
