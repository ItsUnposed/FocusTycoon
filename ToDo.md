# TODO

Planned work for the Python/pygame version. The order below is not chronological
and does not imply priority - items can be picked up and worked on in any order.

## Tycoon overhaul

The Tycoon page (`tycoon/`) gets a full rework: model, simulation, balancing and the
pygame view (`tycoon/ui/`) are all open for redesign. Nothing here is fixed in stone
yet - the current version is a first draft.

## Untis as a second, separate portal

Add WebUntis (timetable / substitution plan) as its own portal integration, next to
the existing Logineo NRW / IServ portal (`portal/`). This should be a separate portal
type, not merged into the existing one, since Untis serves a different purpose
(timetable and substitutions, not homework) and most likely needs its own login flow.

## Popups: add a scrollbar, keep everything else

The tutorial overlay and the small modal windows (`modal_kind` in `game_window.py`,
for example "Connect portal" and "Import from calendar") should stay visually and
functionally the same as they are today - just add a scrollbar to each one, so long
content is not cut off. Do not redesign these windows beyond that.

## Scrollbars: keep mouse control, add keyboard control

Every place that has a scrollbar today (for example the tasks list) should keep
working exactly as it does now with the mouse (wheel + dragging the thumb), and in
addition become scrollable with:

- Page Up / Page Down (scroll by a page)
- Arrow Up / Arrow Down (scroll by a small step)

This applies to the tasks page scrollbar and to the new popup scrollbars above.

## Sound: off by default, one simple toggle button

Sound (`tycoon/ui/tone_player.py`) currently always plays if an audio device is
available. Change this so sound starts **off** by default, and add one simple button
(navbar or similar, next to the existing language dropdown) to turn it on and off.
Keep the toggle itself simple - a single on/off button, no volume slider or settings
menu.

## Full CLAUDE.md compliance pass

Do one full pass over the existing code and check every file against the rules in
`CLAUDE.md` (English only, no decorators, no `lambda`, no dense abbreviations,
generous explanatory comments, simple control flow). Fix anything that does not
match yet, so the whole codebase - not just new code - follows the same style.

## Only give steps an estimated time if one was actually entered

Right now every split-off step seems to get some estimated time regardless of what
was typed into "Estimated time" (`estimate_input` in `game_window.py`). Change the
rule to:

- If the estimated time field is left empty, or has `0` in it, the AI should not
  invent a time at all - the steps get no estimated time.
- Only if the user typed an explicit number greater than 0 should the steps get an
  estimated time. In that case, the AI should split that total across the steps
  itself, based on how much work each step actually is (not just an even split).
- Whatever the AI assigns to the individual steps must add up exactly to the total
  estimated time the user entered - the parts always have to sum to the whole.

This affects the Gemini prompt/response handling in `service/gemini_service.py` and
`service/task_splitter.py`, and how `Task`/`Quest` (`model/task.py`, `model/quest.py`)
store the per-step estimate.
