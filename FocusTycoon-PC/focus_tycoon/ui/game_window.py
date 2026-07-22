"""The main window of Focus Tycoon (pygame).

The app behaves like a tiny website: everything lives in one window, and a navbar
at the top switches between two pages:
  - Tasks: type a big task, split it into steps, tick them off. Finished quests
    move into a "Done" list.
  - Tycoon: the floating islands, embedded, sharing the same gold balance.

Progress (gold, open tasks, Tycoon) is saved through the SaveManager.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import pygame

from . import theme
from .game_state_gold_account import GameStateGoldAccount
from .widgets import Button, Dropdown, SegmentedControl, TextInput
from .. import i18n
from ..model.game_state import GameState
from ..persist.save_manager import SaveManager
from ..service.calendar_import_service import CalendarImportService
from ..service.gemini_service import SPLIT_COARSE, SPLIT_FINE, SPLIT_MEDIUM, SPLIT_NONE
from ..tycoon.tycoon_main import build_panel

DEFAULT_WIDTH = 1300
DEFAULT_HEIGHT = 900
NAVBAR_HEIGHT = 64
COMPOSER_HEIGHT = 660
STAGE_HEIGHT = 78
DONE_CARD_HEIGHT = 64

PAGE_TASKS = "tasks"
PAGE_TYCOON = "tycoon"

# The four choices of the split selector map to these levels.
SPLIT_LEVELS = [SPLIT_NONE, SPLIT_FINE, SPLIT_MEDIUM, SPLIT_COARSE]


def translate(key):
    return i18n.translate(key)


def launch(game, save_manager, saved_game):
    """Build the window and run it. Called from main."""
    window = GameWindow(game, save_manager, saved_game)
    window.run()


class GameWindow:
    def __init__(self, game: GameState, save_manager: SaveManager, saved_game):
        self.game = game
        self.save_manager = save_manager

        pygame.display.set_caption("Focus Tycoon")
        self.width = DEFAULT_WIDTH
        self.height = DEFAULT_HEIGHT
        self.fullscreen = False
        # The window can be resized freely; F11 toggles fullscreen.
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        # The OS can forcibly shrink the requested size (e.g. a small screen);
        # trust whatever we actually got instead of the requested size.
        self.width, self.height = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.running = True

        # The embedded Tycoon page shares the gold balance with the tasks.
        self.tycoon = build_panel(GameStateGoldAccount(game), saved_game)

        self.page = PAGE_TASKS
        self.scroll_y = 0
        self.status = " "
        self.recommended_task_id = -1  # -1 means no task is currently recommended
        # Split level chosen in the composer: index into SPLIT_LEVELS (default = medium).
        self.split_choice_index = 2
        self.is_busy = False  # is a background AI call running right now?

        # Long-lived input widgets.
        self.title_input = TextInput(pygame.Rect(0, 0, 10, 44),
                                     translate("title_placeholder"), on_submit=self.on_split)
        self.description_input = TextInput(pygame.Rect(0, 0, 10, 120),
                                           translate("description_placeholder"), multiline=True)
        self.estimate_input = TextInput(pygame.Rect(0, 0, 10, 44), translate("estimated_time_placeholder"))
        self.split_control = SegmentedControl(self._split_labels(), self.split_choice_index,
                                              self.on_split_choice)

        # Language dropdown (drawn on top of everything so its list is visible).
        language_options = list(i18n.AVAILABLE_LANGUAGES)
        current_index = self._current_language_index(language_options)
        self.language_dropdown = Dropdown(pygame.Rect(0, 0, 120, 32), language_options,
                                          current_index, self.on_language_change)

        # Calendar import.
        self.calendar_import = CalendarImportService()

        # School portal (Logineo / IServ). Only active with a PORTAL_ENCRYPTION_KEY
        # and the cryptography package installed - otherwise it stays disabled.
        self.portal_sync = None
        self.portal_cipher = None
        self.credential_store = None
        self.portal_config = None
        self._init_portal()

        # Background AI calls report their result to the main thread through this queue.
        self.background_results = queue.Queue()

        # Auto-save every 8 seconds.
        self.save_timer = 0.0

        # Click areas rebuilt every frame.
        self.frame_buttons = []
        self.nav_tasks_rect = pygame.Rect(0, 0, 0, 0)
        self.nav_tycoon_rect = pygame.Rect(0, 0, 0, 0)
        self.tutorial_button_rect = pygame.Rect(0, 0, 0, 0)
        # Real position is set every frame in _draw_navbar; start empty so an
        # early click cannot collide with it before the first draw.
        self.sound_button_rect = pygame.Rect(0, 0, 0, 0)

        # Confirm overlay (data reset).
        self.confirm_active = False
        self.confirm_yes_rect = pygame.Rect(0, 0, 0, 0)
        self.confirm_no_rect = pygame.Rect(0, 0, 0, 0)

        # In-app dialogs (portal / calendar) instead of tkinter, so nothing freezes
        # and the dialogs are visible in fullscreen too.
        self.modal_kind = None            # None | "portal" | "calendar"
        self.modal_title = ""
        self.modal_hint = ""
        self.modal_labels = []
        self.modal_buttons = []
        self.modal_inputs = []
        self.modal_segmented = None
        self.modal_segmented_label = ""
        self.modal_submit = None

        # Tutorial overlay.
        self.tutorial_active = False
        self.tutorial_page = 0
        self.tutorial_buttons = []

        # Scrollbar of the tasks page.
        self.scroll_max = 0
        self.scrollbar_thumb = pygame.Rect(0, 0, 0, 0)
        self.scroll_dragging = False
        # Where inside the thumb the mouse grabbed it, so dragging doesn't
        # make the thumb jump to put its top under the cursor.
        self.scroll_drag_offset = 0

    # ---------- helpers for language / split labels ----------

    def _split_labels(self):
        return [translate("split_none"), translate("split_fine"),
                translate("split_medium"), translate("split_coarse")]

    def _current_language_index(self, language_options):
        # Find which dropdown entry matches the currently active language, so
        # the dropdown can open already showing the right selection.
        current = i18n.get_language()
        for index, option in enumerate(language_options):
            if option[0] == current:
                return index
        return 0

    def on_split_choice(self, index):
        self.split_choice_index = index

    def on_language_change(self, index):
        code = i18n.AVAILABLE_LANGUAGES[index][0]
        i18n.set_language(code)
        # Refresh the labels that are stored inside widgets.
        self.title_input.placeholder = translate("title_placeholder")
        self.description_input.placeholder = translate("description_placeholder")
        self.estimate_input.placeholder = translate("estimated_time_placeholder")
        self.split_control.set_labels(self._split_labels())

    # ---------- start / loop ----------

    def run(self):
        while self.running:
            # Seconds since the last frame, used so widget animations (like the
            # blinking text cursor) move at the same speed regardless of frame rate.
            delta_time = self.clock.tick(60) / 1000.0
            events = pygame.event.get()
            self._pre_handle_events(events)
            self._update(delta_time)
            self._draw()
            self._dispatch_events(events)
            pygame.display.flip()
        self._on_close()
        pygame.quit()

    # ---------- events ----------

    def _pre_handle_events(self, events):
        # This is an if/elif chain, so only the first matching branch runs for
        # each event. That gives us a priority order: window-level events first,
        # then whichever overlay/modal is open (it should eat all other input),
        # then scrolling, and only then the normal page widgets.
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self._resize(event.w, event.h)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self._toggle_fullscreen()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._handle_escape()
            elif self.tutorial_active or self.confirm_active:
                pass  # overlays swallow the rest of the input
            elif self.modal_kind is not None:
                # A modal is open: send typing/paste/etc. to its own fields
                # instead of the fields on the page underneath it.
                for text_field in self.modal_inputs:
                    text_field.handle_event(event)
                if self.modal_segmented is not None:
                    self.modal_segmented.handle_event(event)
            elif event.type == pygame.MOUSEWHEEL and self.page == PAGE_TASKS:
                # Clamp so the wheel can't scroll past the top or bottom of the list.
                self.scroll_y = max(0, min(self.scroll_max, self.scroll_y - event.y * 40))
            elif event.type == pygame.MOUSEMOTION and self.scroll_dragging:
                self._drag_scrollbar(event.pos[1])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.scroll_dragging = False  # released the mouse, stop dragging the thumb
            elif self.page == PAGE_TASKS:
                self.title_input.handle_event(event)
                self.description_input.handle_event(event)
                self.estimate_input.handle_event(event)
                self.split_control.handle_event(event)

    def _dispatch_events(self, events):
        for event in events:
            # Clicks are handled here (after drawing), separately from
            # _pre_handle_events, because we need this frame's button rects to
            # know what was actually clicked. We only care about a left click.
            if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
                continue
            position = event.pos

            # The language dropdown is always on top.
            if self.language_dropdown.handle_event(event):
                continue

            if self.tutorial_active:
                self._handle_button_list_click(self.tutorial_buttons, event)
                continue
            if self.modal_kind is not None:
                self._handle_button_list_click(self.modal_buttons, event)
                continue
            if self.confirm_active:
                self._handle_confirm_click(position)
                continue

            if self.page == PAGE_TASKS and self.scrollbar_thumb.collidepoint(position):
                # Clicking the thumb starts a drag instead of clicking whatever is
                # underneath it. Remember where inside the thumb we grabbed it, so
                # the thumb doesn't jump to make its top land under the cursor.
                self.scroll_dragging = True
                self.scroll_drag_offset = position[1] - self.scrollbar_thumb.y
                continue

            if self.nav_tasks_rect.collidepoint(position):
                self.page = PAGE_TASKS
                continue
            if self.nav_tycoon_rect.collidepoint(position):
                self.page = PAGE_TYCOON
                continue
            if self.tutorial_button_rect.collidepoint(position):
                self._open_tutorial()
                continue
            if self.sound_button_rect.collidepoint(position):
                # One click flips sound on/off; the button label updates on the
                # next frame to show the new state.
                self.tycoon.toggle_sound()
                continue

            if self.page == PAGE_TASKS:
                self._handle_button_list_click(self.frame_buttons, event)
            elif self.page == PAGE_TYCOON:
                if self._content_rect().collidepoint(position):
                    self.tycoon.handle_click(position)

    def _handle_button_list_click(self, buttons, event):
        for button in buttons:
            if button.handle_event(event):
                return

    # ---------- window / fullscreen / scrolling ----------

    def _content_rect(self):
        return pygame.Rect(0, NAVBAR_HEIGHT, self.width, self.height - NAVBAR_HEIGHT)

    def _resize(self, width, height):
        # Never let the window shrink below a size where the layout would break.
        self.width = max(900, width)
        self.height = max(600, height)
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        # pygame needs a brand new display surface whenever the mode changes,
        # so we always call set_mode() again instead of just flipping a flag.
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        self.width, self.height = self.screen.get_size()

    def _handle_escape(self):
        # Escape closes whatever is currently "on top", checked in the same
        # order things are drawn on top of each other: tutorial, then modal,
        # then the reset confirmation, and only then leaves fullscreen.
        if self.tutorial_active:
            self.tutorial_active = False
        elif self.modal_kind is not None:
            self._close_modal()
        elif self.confirm_active:
            self.confirm_active = False
        elif self.fullscreen:
            self._toggle_fullscreen()

    def _drag_scrollbar(self, mouse_y):
        # Convert the mouse's position while dragging into a scroll amount, the
        # same way a normal scrollbar works: how far the thumb has moved along
        # its track (as a fraction from 0 to 1) tells us how far to scroll.
        content_rect = self._content_rect()
        track_top = content_rect.y + 4
        track_height = content_rect.height - 8
        # The thumb can only slide within the leftover space once its own
        # height is subtracted from the track - that leftover is "usable".
        usable = track_height - self.scrollbar_thumb.height
        if usable <= 0 or self.scroll_max <= 0:
            return  # nothing to scroll, or the track is too small to drag in
        # Where the top of the thumb would be, relative to the top of the track,
        # if we honor the offset recorded when the drag started.
        relative = (mouse_y - self.scroll_drag_offset) - track_top
        fraction = max(0.0, min(1.0, relative / usable))
        self.scroll_y = int(fraction * self.scroll_max)

    # ---------- update ----------

    def _update(self, delta_time):
        self.title_input.update(delta_time)
        self.description_input.update(delta_time)
        self.estimate_input.update(delta_time)
        for text_field in self.modal_inputs:
            text_field.update(delta_time)
        self.tycoon.update(delta_time)
        # Apply the results of any AI/network calls that finished since the last frame.
        self._drain_background_results()

        self.save_timer += delta_time
        if self.save_timer >= 8.0:
            self.save_timer = 0.0
            self._save()

        # Only show a hand cursor on the Tycoon page, and only when nothing else
        # (a modal or the tutorial) is covering it, so it never lies about what
        # is actually clickable right now.
        if self.page == PAGE_TYCOON and self.modal_kind is None and not self.tutorial_active:
            over_something = self.tycoon.is_over_interactive(pygame.mouse.get_pos())
            wanted = pygame.SYSTEM_CURSOR_HAND if over_something else pygame.SYSTEM_CURSOR_ARROW
        else:
            wanted = pygame.SYSTEM_CURSOR_ARROW
        try:
            pygame.mouse.set_cursor(wanted)
        except pygame.error:
            pass  # not available on some (headless) systems - harmless

    def _drain_background_results(self):
        # Background threads cannot touch pygame or self.status directly, so they
        # just drop their result in this queue. Here, on the main thread, we pick
        # every finished job up and run its callback for real.
        while True:
            try:
                on_done, result = self.background_results.get_nowait()
            except queue.Empty:
                break
            on_done(result)

    def _run_in_background(self, work, on_done):
        """Run work() in a thread and call on_done(result) on the main thread."""
        def runner():
            try:
                result = work()
            except Exception as error:  # noqa: BLE001
                # Catch anything so a failed AI/network call cannot crash the whole
                # app - the error is handed to on_done just like a normal result.
                result = error
            self.background_results.put((on_done, result))

        threading.Thread(target=runner, daemon=True).start()

    # ---------- drawing ----------

    def _draw(self):
        self.screen.fill(theme.BG)
        self._draw_navbar()
        if self.page == PAGE_TASKS:
            self._draw_tasks_page()
        else:
            self._draw_tycoon_page()
        if self.confirm_active:
            self._draw_confirm_overlay()
        if self.modal_kind is not None:
            self._draw_modal()
        if self.tutorial_active:
            self._draw_tutorial()
        # The dropdown is drawn last so its open list stays on top of everything.
        self.language_dropdown.draw(self.screen, pygame.mouse.get_pos())

    def _draw_navbar(self):
        surface = self.screen
        # Draw the navbar background one pixel-row at a time, blending a little
        # further from NAVBAR to BG_ALT on each row, to fake a smooth gradient.
        for y in range(NAVBAR_HEIGHT):
            ratio = y / NAVBAR_HEIGHT
            surface.fill(theme.mix(theme.NAVBAR, theme.BG_ALT, ratio), (0, y, self.width, 1))
        surface.fill(theme.STROKE, (0, NAVBAR_HEIGHT - 1, self.width, 1))

        # Brand on the left.
        theme.draw_text(surface, "◆", 20, theme.ACCENT, 24, 20, bold=True)
        theme.draw_text(surface, "Focus Tycoon", 19, theme.TEXT, 52, 20, bold=True)

        # Segmented navigation in the middle.
        self._draw_nav_buttons()

        # Right side: gold pill, tutorial button, and the language dropdown.
        mouse_pos = pygame.mouse.get_pos()
        gold_text = f"{max(0, self.game.get_gold())} {translate('gold_suffix')}"
        gold_width = theme.text_width(gold_text, 18, bold=True) + 60
        gold_pill = pygame.Rect(self.width - gold_width - 24, 14, gold_width, 36)
        theme.rounded_rect(surface, gold_pill, theme.CARD, 18, theme.STROKE, 1)
        pygame.draw.circle(surface, theme.GOLD, (gold_pill.x + 20, gold_pill.centery), 8)
        theme.draw_text(surface, gold_text, 18, theme.GOLD, gold_pill.x + 36, gold_pill.y + 8, bold=True)

        tutorial_text = translate("tutorial")
        tutorial_width = theme.text_width(tutorial_text, 13, bold=True) + 28
        self.tutorial_button_rect = pygame.Rect(gold_pill.x - tutorial_width - 10, 15, tutorial_width, 34)
        tutorial_color = theme.brighter(theme.CARD_HI, 0.1) if self.tutorial_button_rect.collidepoint(mouse_pos) else theme.CARD_HI
        theme.rounded_rect(surface, self.tutorial_button_rect, tutorial_color, 17)
        theme.draw_text_centered(surface, tutorial_text, 13, theme.TEXT,
                                 self.tutorial_button_rect.centerx, self.tutorial_button_rect.centery, bold=True)

        self.language_dropdown.rect = pygame.Rect(
            self.tutorial_button_rect.x - 130, 16, 120, 32)

        # Sound on/off button, placed just to the left of the language dropdown.
        # Its label already says whether sound is currently on or off, so a
        # single click flips between the two states.
        if self.tycoon.is_sound_enabled():
            sound_text = translate("sound_on")
        else:
            sound_text = translate("sound_off")
        sound_width = theme.text_width(sound_text, 13, bold=True) + 28
        self.sound_button_rect = pygame.Rect(
            self.language_dropdown.rect.x - sound_width - 10, 16, sound_width, 32)
        sound_hovered = self.sound_button_rect.collidepoint(mouse_pos)
        sound_color = theme.brighter(theme.CARD_HI, 0.1) if sound_hovered else theme.CARD_HI
        theme.rounded_rect(surface, self.sound_button_rect, sound_color, 16)
        theme.draw_text_centered(surface, sound_text, 13, theme.TEXT,
                                 self.sound_button_rect.centerx, self.sound_button_rect.centery, bold=True)

    def _draw_nav_buttons(self):
        surface = self.screen
        labels = [(translate("nav_tasks"), PAGE_TASKS), (translate("nav_tycoon"), PAGE_TYCOON)]
        # Measure each label first so the pill background is exactly wide enough
        # to fit both buttons (with padding), instead of using a fixed width.
        widths = [theme.text_width(text, 14, bold=True) + 44 for text, _ in labels]
        total = sum(widths) + 18
        # Center the whole pill horizontally in the navbar.
        container = pygame.Rect((self.width - total) // 2, 12, total, 40)
        theme.rounded_rect(surface, container, theme.PANEL, 20, theme.STROKE, 1)

        x = container.x + 6
        for index, (text, page) in enumerate(labels):
            rect = pygame.Rect(x, container.y + 6, widths[index], 28)
            is_active = self.page == page
            if is_active:
                theme.rounded_rect(surface, rect, theme.ACCENT, 14)
            text_color = theme.BG if is_active else theme.TEXT
            theme.draw_text_centered(surface, text, 14, text_color, rect.centerx, rect.centery, bold=True)
            if page == PAGE_TASKS:
                self.nav_tasks_rect = rect
            else:
                self.nav_tycoon_rect = rect
            x += widths[index] + 6

    def _draw_tycoon_page(self):
        self.tycoon.render(self.screen, self._content_rect())

    # ---------- tasks page ----------

    def _draw_tasks_page(self):
        surface = self.screen
        self.frame_buttons = []
        content_rect = self._content_rect()
        surface.set_clip(content_rect)

        margin = 24
        width = self.width - margin * 2
        y = 20  # in content coordinates (before scrolling)

        y = self._draw_composer(surface, margin, y, width, content_rect)
        y += 16
        y = self._draw_list_header(surface, margin, y, translate("to_do"), theme.TEXT, content_rect)
        y += 10
        y = self._draw_quest_lists(surface, margin, y, width, content_rect)

        # Now that everything has been laid out once, we know the total content
        # height, so we can work out how far scrolling is allowed to go.
        content_height = y + 20
        self.scroll_max = max(0, content_height - content_rect.height)
        if self.scroll_y > self.scroll_max:
            # The content got shorter since the last frame (e.g. a task was
            # completed and its card disappeared) - pull the scroll position
            # back so we are not left looking at empty space.
            self.scroll_y = self.scroll_max

        surface.set_clip(None)
        self._draw_scrollbar(content_rect, content_height)

    def _draw_scrollbar(self, content_rect, content_height):
        if self.scroll_max <= 0:
            # Everything fits on screen already, so there is no thumb to draw
            # or click - make it an empty rect so nothing can collide with it.
            self.scrollbar_thumb = pygame.Rect(0, 0, 0, 0)
            return
        surface = self.screen
        track = pygame.Rect(self.width - 12, content_rect.y + 4, 8, content_rect.height - 8)
        theme.rounded_rect(surface, track, theme.BG_ALT, 4)
        # The thumb's height mirrors how much of the content is visible at
        # once (a short thumb means there is a lot more to scroll through).
        visible_fraction = content_rect.height / content_height
        thumb_height = max(30, int(track.height * visible_fraction))
        # The thumb's position along the track mirrors how far we have scrolled.
        scroll_fraction = self.scroll_y / self.scroll_max
        thumb_y = track.y + int((track.height - thumb_height) * scroll_fraction)
        self.scrollbar_thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_height)
        color = theme.ACCENT if self.scroll_dragging else theme.CARD_HI
        theme.rounded_rect(surface, self.scrollbar_thumb, color, 4)

    def _screen_y(self, content_y, content_rect):
        # Everything on the tasks page is laid out using "content coordinates",
        # as if nothing were ever scrolled. This converts one of those positions
        # into the real on-screen position, by shifting it up by the scroll amount.
        return content_rect.y + content_y - self.scroll_y

    def _draw_composer(self, surface, x, content_y, width, content_rect):
        card_rect = pygame.Rect(x, self._screen_y(content_y, content_rect), width, COMPOSER_HEIGHT)
        theme.rounded_rect(surface, card_rect, theme.PANEL, 18, theme.STROKE, 1)

        inner_x = card_rect.x + 22
        inner_width = card_rect.width - 44
        # cursor_y works like a pen moving down the card: we draw one row, then
        # move the cursor down by that row's height before drawing the next one.
        cursor_y = card_rect.y + 18

        theme.draw_text(surface, translate("plan_new_task"), 18, theme.TEXT, inner_x, cursor_y, bold=True)
        cursor_y += 28
        theme.draw_text(surface, translate("composer_subtitle"), 13, theme.MUTED, inner_x, cursor_y)
        cursor_y += 28

        # Title row: field + submit button.
        theme.draw_text(surface, translate("title_label"), 13, theme.TEXT, inner_x, cursor_y, bold=True)
        cursor_y += 24
        submit_text = translate("break_into_steps")
        submit_width = theme.text_width(submit_text, 13, bold=True) + 36
        self.title_input.set_rect(pygame.Rect(inner_x, cursor_y, inner_width - submit_width - 10, 44))
        self.title_input.draw(surface)
        submit_rect = pygame.Rect(inner_x + inner_width - submit_width, cursor_y, submit_width, 44)
        self._add_button(submit_rect, submit_text, theme.ACCENT, (255, 255, 255),
                         self.on_split, enabled=not self.is_busy)
        cursor_y += 58

        # Description.
        theme.draw_text(surface, translate("description_label"), 13, theme.TEXT, inner_x, cursor_y, bold=True)
        cursor_y += 24
        self.description_input.set_rect(pygame.Rect(inner_x, cursor_y, inner_width, 120))
        self.description_input.draw(surface)
        cursor_y += 134

        # Split selector: Do not split / Fine / Medium / Coarse.
        theme.draw_text(surface, translate("split_label"), 13, theme.TEXT, inner_x, cursor_y, bold=True)
        cursor_y += 26
        self.split_control.draw(surface, inner_x, cursor_y)
        cursor_y += 54

        # Estimated time + AI estimate.
        theme.draw_text(surface, translate("estimated_time_label"), 13, theme.TEXT, inner_x, cursor_y, bold=True)
        cursor_y += 24
        estimate_button_text = translate("ai_estimate")
        estimate_button_width = theme.text_width(estimate_button_text, 13, bold=True) + 36
        self.estimate_input.set_rect(pygame.Rect(inner_x, cursor_y, inner_width - estimate_button_width - 10, 44))
        self.estimate_input.draw(surface)
        estimate_rect = pygame.Rect(inner_x + inner_width - estimate_button_width, cursor_y, estimate_button_width, 44)
        self._add_button(estimate_rect, estimate_button_text, theme.CARD_HI, theme.TEXT,
                         self.on_estimate_time, enabled=not self.is_busy)
        cursor_y += 58

        # Action row: recommend left, reset right.
        recommend_text = translate("what_first")
        recommend_width = theme.text_width(recommend_text, 13, bold=True) + 36
        self._add_button(pygame.Rect(inner_x, cursor_y, recommend_width, 44), recommend_text,
                         theme.CARD_HI, theme.TEXT, self.on_recommend)
        reset_text = translate("reset_all")
        reset_width = theme.text_width(reset_text, 13, bold=True) + 36
        self._add_button(pygame.Rect(inner_x + inner_width - reset_width, cursor_y, reset_width, 44),
                         reset_text, theme.RESET_BG, theme.RESET_FG, self.on_reset_data)
        cursor_y += 54

        # Import row (three buttons side by side).
        import_buttons = [
            (translate("import_calendar"), self.on_import_calendar, theme.CARD_HI, theme.TEXT),
            (translate("connect_portal"), self.on_connect_portal, theme.CARD, theme.MUTED),
            (translate("sync_portal"), self.on_sync_portal, theme.CARD_HI, theme.TEXT),
        ]
        button_width = (inner_width - 6 * 2) // 3
        # button_x is the same kind of cursor as cursor_y, but moving sideways
        # across the row instead of down the card.
        button_x = inner_x
        for label, action, background, foreground in import_buttons:
            self._add_button(pygame.Rect(button_x, cursor_y, button_width, 40), label, background, foreground, action)
            button_x += button_width + 6
        cursor_y += 48

        # Status line.
        theme.draw_text(surface, self.status, 12, theme.MUTED, inner_x, cursor_y)

        return content_y + COMPOSER_HEIGHT

    def _draw_list_header(self, surface, x, content_y, text, color, content_rect):
        screen_y = self._screen_y(content_y, content_rect)
        pygame.draw.circle(surface, color, (x + 5, screen_y + 12), 5)
        theme.draw_text(surface, text, 17, theme.TEXT, x + 18, screen_y, bold=True)
        return content_y + 30

    def _draw_quest_lists(self, surface, x, content_y, width, content_rect):
        active_quests = [quest for quest in self.game.get_quests() if not quest.is_completed()]
        done_quests = [quest for quest in self.game.get_quests() if quest.is_completed()]

        # Not-yet-split portal homework goes first (the hybrid inbox).
        open_homework = [homework_item for homework_item in self.game.get_imported_homework()
                         if not homework_item.decomposed]
        for homework in open_homework:
            content_y = self._draw_homework_card(surface, x, content_y, width, homework, content_rect)
            content_y += 12

        if not active_quests and not open_homework:
            content_y = self._draw_placeholder(surface, x, content_y, translate("no_open_quests"), content_rect)
        else:
            for quest in active_quests:
                content_y = self._draw_quest_group(surface, x, content_y, width, quest, content_rect)
                content_y += 14

        content_y += 8
        content_y = self._draw_list_header(surface, x, content_y, translate("done"), theme.SUCCESS, content_rect)
        content_y += 10

        if not done_quests:
            content_y = self._draw_placeholder(surface, x, content_y, translate("nothing_done"), content_rect)
        else:
            for quest in done_quests:
                content_y = self._draw_done_card(surface, x, content_y, width, quest, content_rect)
                content_y += 10
        return content_y

    def _draw_quest_group(self, surface, x, content_y, width, quest, content_rect):
        stage_count = quest.get_stage_count()
        # We need the card's total height before we can draw its rounded
        # background, so add up every part that goes inside it: top/bottom
        # padding, the title row, the progress bar and its spacing, and then
        # one stage card per step (with a small gap between each of them).
        group_height = 16 * 2 + 22 + 10 + 9 + 12 + stage_count * STAGE_HEIGHT + max(0, stage_count - 1) * 8
        group_rect = pygame.Rect(x, self._screen_y(content_y, content_rect), width, group_height)
        theme.rounded_rect(surface, group_rect, theme.CARD, 16, theme.STROKE, 1)

        inner_x = group_rect.x + 18
        inner_width = group_rect.width - 36
        # cursor_y tracks where to draw next, moving down the card step by step.
        cursor_y = group_rect.y + 16

        theme.draw_text(surface, quest.title, 16, theme.TEXT, inner_x, cursor_y, bold=True)
        progress_text = f"{quest.get_completed_count()} / {quest.get_stage_count()}"
        progress_color = theme.SUCCESS if quest.is_completed() else theme.MUTED
        progress_width = theme.text_width(progress_text, 13, bold=True)
        theme.draw_text(surface, progress_text, 13, progress_color,
                        inner_x + inner_width - progress_width, cursor_y + 2, bold=True)
        cursor_y += 32

        self._draw_progress_bar(surface, inner_x, cursor_y, inner_width,
                                quest.get_completed_count(), quest.get_stage_count())
        cursor_y += 21

        stages = quest.get_stages()
        for index, task in enumerate(stages):
            # The "recommended" tag only shows on the one task the recommend
            # button pointed at, and only while it is still unfinished.
            is_recommended = task.id == self.recommended_task_id and not task.completed
            self._draw_stage_card(surface, inner_x, cursor_y, inner_width, task, index, len(stages), is_recommended)
            cursor_y += STAGE_HEIGHT + 8

        return content_y + group_height

    def _draw_stage_card(self, surface, x, y, width, task, index, count, is_recommended):
        card = pygame.Rect(x, y, width, STAGE_HEIGHT)
        fill = theme.CARD_HI if is_recommended else theme.PANEL
        border = theme.GOLD if is_recommended else theme.STROKE
        theme.rounded_rect(surface, card, fill, 12, border, 1)

        # Order arrows on the left.
        arrow_x = card.x + 12
        up_rect = pygame.Rect(arrow_x, card.y + 14, 30, 20)
        down_rect = pygame.Rect(arrow_x, card.y + 40, 30, 20)
        # You can't move a step above the first one or below the last one, and
        # a finished step can no longer be reordered at all.
        up_enabled = index > 0 and not task.completed
        down_enabled = index < count - 1 and not task.completed
        self._draw_arrow_button(surface, up_rect, "▲", up_enabled, task.id, True)
        self._draw_arrow_button(surface, down_rect, "▼", down_enabled, task.id, False)

        info_x = card.x + 54
        info_y = card.y + 8
        if is_recommended:
            theme.draw_text(surface, translate("recommended"), 10, theme.GOLD, info_x, info_y, bold=True)
            info_y += 14

        title_color = theme.MUTED if task.completed else theme.TEXT
        theme.draw_text(surface, task.title, 14, title_color, info_x, info_y, bold=True)
        if task.completed:
            title_width = theme.text_width(task.title, 14, bold=True)
            strike_y = info_y + 9
            pygame.draw.line(surface, theme.MUTED, (info_x, strike_y), (info_x + title_width, strike_y), 1)
        info_y += 20

        # The detail line (short) - the longer AI explanation for this step.
        if task.detail:
            theme.draw_text(surface, self._shorten(task.detail, 70), 12, theme.MUTED, info_x, info_y)
            info_y += 18
        # A step may have no estimated time at all. In that case we use a
        # shorter meta line that leaves the minutes out completely.
        if task.estimated_minutes is None:
            meta = translate("meta_line_no_time").format(
                level=self._split_level_name(task.energy_level),
                gold=task.gold_reward)
        else:
            meta = translate("meta_line").format(
                level=self._split_level_name(task.energy_level),
                minutes=task.estimated_minutes, gold=task.gold_reward)
        theme.draw_text(surface, meta, 11, theme.MUTED, info_x, info_y)

        # Right side: a done button or a checkmark.
        if task.completed:
            theme.draw_text(surface, translate("completed_short"), 13, theme.SUCCESS,
                            card.right - 100, card.centery - 8, bold=True)
        else:
            button_text = translate("done_button")
            button_width = theme.text_width(button_text, 13, bold=True) + 30
            button_rect = pygame.Rect(card.right - button_width - 12, card.centery - 17, button_width, 34)
            task_id = task.id

            def complete_this():
                self.on_complete_task(task_id)

            self._add_button(button_rect, button_text, theme.SUCCESS, (255, 255, 255), complete_this)

    def _draw_arrow_button(self, surface, rect, glyph, enabled, task_id, move_up):
        color = theme.PANEL if not enabled else theme.CARD_HI
        theme.rounded_rect(surface, rect, color, 8)
        theme.draw_text_centered(surface, glyph, 10, theme.TEXT if enabled else theme.MUTED,
                                 rect.centerx, rect.centery, bold=True)
        if enabled:
            if move_up:
                def do_move():
                    self.on_move_up(task_id)
            else:
                def do_move():
                    self.on_move_down(task_id)
            # We already drew the arrow glyph ourselves above, so this just
            # registers an invisible, same-colored button over it to catch clicks.
            self._add_button(rect, "", color, color, do_move, draw=False)

    def _draw_done_card(self, surface, x, content_y, width, quest, content_rect):
        card = pygame.Rect(x, self._screen_y(content_y, content_rect), width, DONE_CARD_HEIGHT)
        theme.rounded_rect(surface, card, theme.DONE_CARD_BG, 14, theme.DONE_CARD_BORDER, 1)

        theme.draw_text(surface, "✓", 24, theme.SUCCESS, card.x + 18, card.centery - 16, bold=True)
        info_x = card.x + 54
        theme.draw_text(surface, quest.title, 15, theme.TEXT, info_x, card.y + 12, bold=True)
        # Add up the gold reward from every step to show the total this quest earned.
        earned = sum(task.gold_reward for task in quest.get_stages())
        subtitle = translate("steps_done_earned").format(count=quest.get_stage_count(), gold=earned)
        theme.draw_text(surface, subtitle, 12, theme.MUTED, info_x, card.y + 34)
        badge = translate("finished_badge")
        badge_width = theme.text_width(badge, 11, bold=True)
        theme.draw_text(surface, badge, 11, theme.SUCCESS, card.right - badge_width - 18, card.centery - 6, bold=True)
        return content_y + DONE_CARD_HEIGHT

    def _draw_homework_card(self, surface, x, content_y, width, homework, content_rect):
        card = pygame.Rect(x, self._screen_y(content_y, content_rect), width, 72)
        theme.rounded_rect(surface, card, theme.CARD_HI, 12, theme.GOLD, 1)

        info_x = card.x + 16
        theme.draw_text(surface, translate("portal_homework"), 10, theme.GOLD, info_x, card.y + 12, bold=True)
        theme.draw_text(surface, homework.title, 14, theme.TEXT, info_x, card.y + 28, bold=True)
        due_text = translate("due").format(date=homework.due_date.strftime("%d.%m.%Y"))
        theme.draw_text(surface, f"{homework.subject}   ·   {due_text}", 12, theme.MUTED, info_x, card.y + 48)

        button_text = translate("split_button")
        button_width = theme.text_width(button_text, 13, bold=True) + 30
        button_rect = pygame.Rect(card.right - button_width - 14, card.centery - 17, button_width, 34)
        external_id = homework.external_portal_id

        def split_this():
            self.on_decompose_homework(external_id)

        self._add_button(button_rect, button_text, theme.ACCENT, (255, 255, 255), split_this)
        return content_y + 72

    def _draw_placeholder(self, surface, x, content_y, text, content_rect):
        theme.draw_text(surface, text, 13, theme.MUTED, x + 6, self._screen_y(content_y, content_rect))
        return content_y + 34

    def _draw_progress_bar(self, surface, x, y, width, done, total):
        height = 9
        theme.rounded_rect(surface, pygame.Rect(x, y, width, height), theme.BG_ALT, height // 2)
        # A quest with zero stages would otherwise divide by zero here.
        fraction = 0 if total == 0 else done / total
        fill_width = int(width * fraction)
        if done > 0:
            # Even a tiny fraction should still show a visible sliver of fill
            # (a rounded bar that is thinner than it is tall looks broken).
            fill_width = max(fill_width, height)
            color = theme.SUCCESS if done >= total else theme.ACCENT
            theme.rounded_rect(surface, pygame.Rect(x, y, min(fill_width, width), height), color, height // 2)

    def _add_button(self, rect, text, background, foreground, on_click, enabled=True, draw=True):
        content_rect = self._content_rect()
        if rect.bottom < content_rect.top or rect.top > content_rect.bottom:
            return  # off-screen (scrolled away) - not clickable
        button = Button(rect, text, background, foreground, on_click, enabled)
        if draw:
            button.draw(self.screen, pygame.mouse.get_pos())
        self.frame_buttons.append(button)

    # ---------- confirm overlay (data reset) ----------

    def _draw_confirm_overlay(self):
        surface = self.screen
        # A semi-transparent black rectangle over the whole window, so the page
        # underneath is still visible but clearly "disabled" behind the popup.
        veil = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        surface.blit(veil, (0, 0))

        box = pygame.Rect(0, 0, 560, 240)
        box.center = (self.width // 2, self.height // 2)
        theme.rounded_rect(surface, box, theme.PANEL, 18, theme.STROKE, 1)

        theme.draw_text(surface, translate("reset_title"), 20, theme.TEXT, box.x + 28, box.y + 24, bold=True)
        lines = [translate("reset_confirm"), "", translate("reset_warning1"), translate("reset_warning2")]
        # cursor_y walks down the box, one text line at a time.
        cursor_y = box.y + 62
        for line in lines:
            theme.draw_text(surface, line, 13, theme.MUTED, box.x + 28, cursor_y)
            cursor_y += 22

        self.confirm_no_rect = pygame.Rect(box.right - 260, box.bottom - 58, 110, 38)
        self.confirm_yes_rect = pygame.Rect(box.right - 140, box.bottom - 58, 120, 38)
        theme.rounded_rect(surface, self.confirm_no_rect, theme.CARD_HI, 19)
        theme.draw_text_centered(surface, translate("cancel"), 13, theme.TEXT,
                                 self.confirm_no_rect.centerx, self.confirm_no_rect.centery, bold=True)
        theme.rounded_rect(surface, self.confirm_yes_rect, theme.RESET_BG, 19)
        theme.draw_text_centered(surface, translate("reset_all"), 13, theme.RESET_FG,
                                 self.confirm_yes_rect.centerx, self.confirm_yes_rect.centery, bold=True)

    def _handle_confirm_click(self, position):
        if self.confirm_yes_rect.collidepoint(position):
            self.confirm_active = False
            self._perform_reset()
        elif self.confirm_no_rect.collidepoint(position):
            self.confirm_active = False

    # ---------- tutorial overlay ----------

    def _open_tutorial(self):
        self.tutorial_active = True
        self.tutorial_page = 0

    def _draw_tutorial(self):
        surface = self.screen
        veil = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        surface.blit(veil, (0, 0))

        pages = i18n.get_tutorial_pages()
        # Defensive clamp: if the language changed and the new tutorial has
        # fewer pages, don't let the page index point past the last one.
        if self.tutorial_page >= len(pages):
            self.tutorial_page = len(pages) - 1
        page = pages[self.tutorial_page]

        box = pygame.Rect(0, 0, 720, 460)
        box.center = (self.width // 2, self.height // 2)
        theme.rounded_rect(surface, box, theme.PANEL, 18, theme.STROKE, 1)

        theme.draw_text(surface, page["title"], 22, theme.TEXT, box.x + 32, box.y + 26, bold=True)
        theme.draw_text(surface, f"{self.tutorial_page + 1} / {len(pages)}", 12, theme.MUTED,
                        box.right - 70, box.y + 32)
        # cursor_y walks down the box, one text line at a time.
        cursor_y = box.y + 72
        for line in page["lines"]:
            theme.draw_text(surface, line, 14, theme.MUTED, box.x + 32, cursor_y)
            cursor_y += 26

        self.tutorial_buttons = []
        mouse_pos = pygame.mouse.get_pos()
        # Previous / Next / Close buttons.
        close_rect = pygame.Rect(box.right - 130, box.bottom - 56, 100, 38)
        close_button = Button(close_rect, translate("cancel"), theme.CARD_HI, theme.TEXT, self._close_tutorial)
        close_button.draw(surface, mouse_pos)
        self.tutorial_buttons.append(close_button)

        if self.tutorial_page > 0:
            prev_rect = pygame.Rect(box.x + 32, box.bottom - 56, 90, 38)
            prev_button = Button(prev_rect, "◀", theme.CARD, theme.TEXT, self._tutorial_prev)
            prev_button.draw(surface, mouse_pos)
            self.tutorial_buttons.append(prev_button)
        if self.tutorial_page < len(pages) - 1:
            next_rect = pygame.Rect(box.x + 130, box.bottom - 56, 90, 38)
            next_button = Button(next_rect, "▶", theme.ACCENT, (255, 255, 255), self._tutorial_next)
            next_button.draw(surface, mouse_pos)
            self.tutorial_buttons.append(next_button)

    def _tutorial_prev(self):
        if self.tutorial_page > 0:
            self.tutorial_page -= 1

    def _tutorial_next(self):
        self.tutorial_page += 1

    def _close_tutorial(self):
        self.tutorial_active = False

    # ---------- in-app modals ----------

    def _open_calendar_modal(self):
        source_field = TextInput(pygame.Rect(0, 0, 10, 44), translate("calendar_source_placeholder"))
        source_field.focused = True
        self.modal_kind = "calendar"
        self.modal_title = translate("import_calendar_title")
        self.modal_hint = ""
        self.modal_labels = [translate("calendar_source_label")]
        self.modal_inputs = [source_field]
        # The calendar modal has its own split selector.
        self.modal_segmented = SegmentedControl(self._split_labels(), self.split_choice_index)
        self.modal_segmented_label = translate("split_label")

        def submit():
            level = SPLIT_LEVELS[self.modal_segmented.selected_index]
            self._do_calendar_import(source_field.text, level)

        self.modal_submit = submit

    def _open_portal_modal(self):
        username_field = TextInput(pygame.Rect(0, 0, 10, 44), translate("portal_username"))
        password_field = TextInput(pygame.Rect(0, 0, 10, 44), translate("portal_password"), mask=True)
        logineo_field = TextInput(pygame.Rect(0, 0, 10, 44), "https://...")
        iserv_field = TextInput(pygame.Rect(0, 0, 10, 44), "https://...")
        username_field.focused = True

        # Pre-fill the URLs from the config, if present.
        from ..portal.portal_type import PortalType
        if self.portal_config is not None:
            logineo_field.text = self.portal_config.school_url(PortalType.LOGINEO_NRW) or ""
            iserv_field.text = self.portal_config.school_url(PortalType.ISERV) or ""

        self.modal_kind = "portal"
        self.modal_title = translate("connect_portal_title")
        self.modal_hint = translate("portal_hint")
        self.modal_labels = [translate("portal_username"), translate("portal_password"),
                             translate("portal_logineo_url"), translate("portal_iserv_url")]
        self.modal_inputs = [username_field, password_field, logineo_field, iserv_field]
        self.modal_segmented = None
        self.modal_segmented_label = ""

        def submit():
            self._do_portal_connect(username_field.text, password_field.text,
                                    logineo_field.text, iserv_field.text)

        self.modal_submit = submit

    def _close_modal(self):
        self.modal_kind = None
        self.modal_inputs = []
        self.modal_buttons = []
        self.modal_segmented = None
        self.modal_submit = None

    def _confirm_modal(self):
        # Grab the submit callback before closing, since closing clears
        # self.modal_submit to None - then run it after the modal is gone.
        submit = self.modal_submit
        self._close_modal()
        if submit is not None:
            submit()

    def _draw_modal(self):
        surface = self.screen
        veil = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        surface.blit(veil, (0, 0))

        # This one dialog box is reused for both the calendar and portal
        # modals, which need different amounts of space - so its height is
        # calculated from how many fields, and which optional parts, it has.
        field_count = len(self.modal_inputs)
        extra = 78 if self.modal_segmented is not None else 0
        hint_extra = 24 if self.modal_hint else 0
        box = pygame.Rect(0, 0, 640, 130 + field_count * 78 + extra + hint_extra + 60)
        box.center = (self.width // 2, self.height // 2)
        theme.rounded_rect(surface, box, theme.PANEL, 18, theme.STROKE, 1)

        inner_x = box.x + 28
        inner_width = box.width - 56
        # cursor_y walks down the box as we draw each part, same as elsewhere.
        cursor_y = box.y + 24
        theme.draw_text(surface, self.modal_title, 20, theme.TEXT, inner_x, cursor_y, bold=True)
        cursor_y += 34
        if self.modal_hint:
            theme.draw_text(surface, self.modal_hint, 12, theme.MUTED, inner_x, cursor_y)
            cursor_y += 24

        if self.modal_segmented is not None:
            theme.draw_text(surface, self.modal_segmented_label, 13, theme.TEXT, inner_x, cursor_y, bold=True)
            cursor_y += 26
            self.modal_segmented.draw(surface, inner_x, cursor_y)
            cursor_y += 52

        for label, text_field in zip(self.modal_labels, self.modal_inputs):
            theme.draw_text(surface, label, 13, theme.TEXT, inner_x, cursor_y, bold=True)
            cursor_y += 24
            text_field.set_rect(pygame.Rect(inner_x, cursor_y, inner_width, 44))
            text_field.draw(surface)
            cursor_y += 54

        confirm_text = translate("confirm")
        cancel_text = translate("cancel")
        confirm_width = theme.text_width(confirm_text, 13, bold=True) + 40
        cancel_width = theme.text_width(cancel_text, 13, bold=True) + 40
        confirm_rect = pygame.Rect(box.right - confirm_width - 24, box.bottom - 56, confirm_width, 38)
        cancel_rect = pygame.Rect(confirm_rect.x - cancel_width - 12, box.bottom - 56, cancel_width, 38)
        mouse_pos = pygame.mouse.get_pos()
        cancel_button = Button(cancel_rect, cancel_text, theme.CARD_HI, theme.TEXT, self._close_modal)
        confirm_button = Button(confirm_rect, confirm_text, theme.ACCENT, (255, 255, 255), self._confirm_modal)
        cancel_button.draw(surface, mouse_pos)
        confirm_button.draw(surface, mouse_pos)
        self.modal_buttons = [cancel_button, confirm_button]

    # ---------- actions ----------

    def on_split(self):
        title = self.title_input.text.strip()
        if not title:
            self.status = "Please enter a title first."
            return
        description = self.description_input.text.strip()
        split_level = SPLIT_LEVELS[self.split_choice_index]
        minutes = self._parse_minutes(self.estimate_input.text)
        # is_busy disables the split/estimate buttons (see _draw_composer) while
        # this call is running, so the user can't fire off a second AI request
        # before the first one is done. The actual call runs on a background
        # thread (see _run_in_background) so the window keeps responding.
        self.is_busy = True
        self.status = "Splitting the task ..."

        def work():
            return self.game.process_new_task(title, description, split_level, minutes)

        def done(result):
            self.is_busy = False
            if isinstance(result, Exception):
                self.status = f"Error: {result}"
                return
            self.status = f'Quest "{result.title}" created with {result.get_stage_count()} steps.'
            self.title_input.text = ""
            self.description_input.text = ""
            self.estimate_input.text = ""
            self._save()

        self._run_in_background(work, done)

    def on_estimate_time(self):
        title = self.title_input.text.strip()
        if not title:
            self.status = "Please enter a title first so the AI can estimate."
            return
        description = self.description_input.text.strip()
        self.is_busy = True
        self.status = "The AI is estimating the duration ..."

        def work():
            return self.game.estimate_minutes(title, description)

        def done(result):
            self.is_busy = False
            if isinstance(result, Exception):
                self.status = f"Error while estimating: {result}"
            elif result is not None:
                self.estimate_input.text = str(result)
                self.status = f"AI estimate: {result} minutes."
            else:
                self.status = "AI estimate is not available."

        self._run_in_background(work, done)

    def on_recommend(self):
        recommendation = self.game.recommend_next_task()
        if recommendation is not None:
            self.recommended_task_id = recommendation.id
            # The recommended step might have no estimated time, so only mention
            # the minutes when we actually have them.
            if recommendation.estimated_minutes is None:
                self.status = (f'Recommendation: "{recommendation.title}" - '
                               "a small step for a quick win.")
            else:
                self.status = (f'Recommendation: "{recommendation.title}" - the smallest step '
                               f"({recommendation.estimated_minutes} min) for a quick win.")
        else:
            self.recommended_task_id = -1
            self.status = "All done - great! Type a new task."

    def on_move_up(self, task_id):
        self.game.move_stage_up(task_id)

    def on_move_down(self, task_id):
        self.game.move_stage_down(task_id)

    def on_complete_task(self, task_id):
        # Check whether the quest was already fully done before this step, so
        # afterwards we can tell the difference between "just one more step
        # done" and "that was the last step - the whole quest just finished".
        quest = self.game.find_quest_containing(task_id)
        was_complete = quest.is_completed() if quest is not None else False
        if self.game.complete_task(task_id):
            task = self.game.find_task(task_id)
            now_complete = quest.is_completed() if quest is not None else False
            if now_complete and not was_complete:
                self.status = f"Quest finished - great! +{task.gold_reward} gold. Moved to 'Done'."
            else:
                self.status = f"Done: +{task.gold_reward} gold!"
            if task_id == self.recommended_task_id:
                self.recommended_task_id = -1
            self._save()

    def on_reset_data(self):
        self.confirm_active = True

    def _perform_reset(self):
        self.save_manager.delete()
        self.game.reset()
        self.recommended_task_id = -1
        self.tycoon.shutdown()
        self.tycoon = build_panel(GameStateGoldAccount(self.game), None)
        self.status = "All data has been reset."
        self.page = PAGE_TASKS
        self.scroll_y = 0

    # ---------- calendar / portal ----------

    def on_import_calendar(self):
        self._open_calendar_modal()

    def _do_calendar_import(self, source, split_level):
        source = source.strip()
        if not source:
            self.status = "Please enter a file path or a subscription URL."
            return
        # The user can point us at either a local .ics file or a calendar
        # subscription URL - tell them apart by how the text starts.
        is_url = source.lower().startswith(("http://", "https://", "webcal://"))
        self.status = "Loading the calendar ..."

        def work():
            if is_url:
                all_events = self.calendar_import.load_from_url(source)
            else:
                all_events = self.calendar_import.load_from_file(Path(source))
            upcoming = self.calendar_import.filter_upcoming(all_events)
            new_count = 0
            duplicate_count = 0
            for event in upcoming:
                if self.game.import_from_calendar([event], split_level):
                    new_count += 1
                else:
                    duplicate_count += 1
            return new_count, duplicate_count

        def done(result):
            if isinstance(result, Exception):
                self.status = f"Calendar import failed: {result}"
                return
            new_count, duplicate_count = result
            if new_count == 0 and duplicate_count == 0:
                self.status = "No upcoming events found in the time window."
            else:
                text = f"{new_count} event(s) imported and split into quests."
                if duplicate_count > 0:
                    text += f" {duplicate_count} duplicate(s) skipped."
                self.status = text
            self._save()

        self._run_in_background(work, done)

    def _init_portal(self):
        try:
            from ..portal import portal_config
            from ..portal.credential_store import CredentialStore

            self.portal_config = portal_config.load()
            self.credential_store = CredentialStore()
            if not self.portal_config.has_encryption_key():
                return
            from ..portal.credential_cipher import CredentialCipher
            from ..portal.game_state_task_sink import GameStateTaskSink
            from ..portal.portal_sync_service import with_defaults

            self.portal_cipher = CredentialCipher(self.portal_config.encryption_key())
            self.portal_sync = with_defaults(
                self.credential_store, self.portal_cipher, GameStateTaskSink(self.game))
            self._apply_portal_auto_sync()
        except Exception:  # noqa: BLE001 - e.g. the cryptography package is missing
            self.portal_sync = None
            self.portal_cipher = None

    def _apply_portal_auto_sync(self):
        if self.portal_sync is None:
            return
        if not self.credential_store.load_all():
            # No saved logins yet, so there is nothing to sync automatically.
            self.portal_sync.stop_auto_sync()
            return

        def on_result(result):
            # This callback runs on the portal sync's own background thread, so
            # it cannot touch self.status directly. We reuse the same
            # background_results queue as our other background work, which
            # picks jobs up on the main thread. The queue always calls its
            # callback with one argument, but we already have "result" from the
            # closure above, so "apply" just ignores the argument it is given.
            def apply(_ignored):
                if result.has_changes() or result.messages:
                    self.status = "Portal auto-sync: " + result.summarize()
            self.background_results.put((apply, None))

        from ..portal.portal_sync_service import DEFAULT_AUTO_SYNC_MINUTES
        self.portal_sync.start_auto_sync(DEFAULT_AUTO_SYNC_MINUTES, on_result)

    def on_connect_portal(self):
        if self.portal_cipher is None:
            self.status = "Portal disabled: set PORTAL_ENCRYPTION_KEY in ~/.focustycoon/portal.env."
            return
        self._open_portal_modal()

    def _do_portal_connect(self, username, password, logineo_url, iserv_url):
        from ..portal import portal_urls
        from ..portal.credential_store import Credential
        from ..portal.portal_exception import PortalException
        from ..portal.portal_type import PortalType

        username = username.strip()
        if not username or not password:
            self.status = "Please enter a username and a password."
            return

        # One login, but it can cover both portals (same user + password, two URLs).
        targets = []
        if logineo_url.strip():
            targets.append((PortalType.LOGINEO_NRW, logineo_url.strip()))
        if iserv_url.strip():
            targets.append((PortalType.ISERV, iserv_url.strip()))
        if not targets:
            self.status = "Please enter at least one school URL (Logineo or IServ)."
            return

        connected_names = []
        for portal_type, url in targets:
            try:
                origin = portal_urls.origin_of(url)
            except PortalException as error:
                self.status = error.user_message
                return
            encrypted = self.portal_cipher.encrypt(password)
            self.credential_store.save(Credential(portal_type, username, encrypted, origin, None, None))
            connected_names.append(portal_type.display_name)

        self.status = "Connected: " + ", ".join(connected_names) + ". Now press 'Sync portal'."
        self._apply_portal_auto_sync()

    def on_sync_portal(self):
        if self.portal_sync is None:
            self.status = "Portal disabled: set PORTAL_ENCRYPTION_KEY in ~/.focustycoon/portal.env."
            return
        connected = self.credential_store.load_all()
        if not connected:
            self.status = "No portal credentials found. Please connect a portal first."
            return
        portals = list(connected.keys())
        self.status = "Syncing portal(s) ..."

        from ..portal.portal_exception import PortalException

        def work():
            parts = []
            for portal_type in portals:
                try:
                    result = self.portal_sync.sync(portal_type, False)
                    parts.append(f"{portal_type.display_name}: {result.message}")
                except PortalException as error:
                    parts.append(f"{portal_type.display_name}: {error.user_message}")
            return "   |   ".join(parts)

        def done(result):
            if isinstance(result, Exception):
                self.status = f"Portal sync failed: {result}"
            else:
                self.status = result
            self._save()

        self._run_in_background(work, done)

    def on_decompose_homework(self, external_id):
        split_level = SPLIT_LEVELS[self.split_choice_index]
        self.status = "Splitting the homework ..."

        def work():
            return self.game.decompose_imported_homework(external_id, split_level)

        def done(result):
            if isinstance(result, Exception):
                self.status = f"Error while splitting: {result}"
                return
            if result is not None:
                self.status = f'Homework split: "{result.title}" ({result.get_stage_count()} steps).'
            else:
                self.status = "Homework was already split."
            self._save()

        self._run_in_background(work, done)

    # ---------- small helpers ----------

    def _split_level_name(self, energy_level):
        # energy_level is stored as 1 (fine), 2 (medium) or 3 (coarse). Clamp it
        # into that range first in case older save data has something outside
        # it, then shift down by one to get a valid list index (0, 1 or 2).
        index = max(1, min(3, energy_level)) - 1
        level_names = [translate("split_fine"), translate("split_medium"), translate("split_coarse")]
        return level_names[index]

    def _shorten(self, text, max_chars):
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 1] + "…"

    def _parse_minutes(self, text):
        if not text or not text.strip():
            return 0
        try:
            return max(0, int(text.strip()))
        except ValueError:
            return 0

    def _save(self):
        self.save_manager.save(self.game, self.tycoon.state)

    def _on_close(self):
        self._save()
        if self.portal_sync is not None:
            self.portal_sync.shutdown()
        self.tycoon.shutdown()
