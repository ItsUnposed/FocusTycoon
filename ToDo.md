# TODO

Planned work for the Python/pygame version. The order below is not chronological
and does not imply priority - items can be picked up and worked on in any order.
The items near the very bottom ("later / bigger") are meant to come last.

## Tycoon overhaul

The Tycoon page (`tycoon/`) was reworked into an isometric city builder, but it is
still open for iteration: model, simulation, balancing and the pygame view
(`tycoon/ui/`) can all keep changing. The items below are the concrete next steps.

## Business tycoon: grants and investors

The electrical-engineering business tycoon (`business_*` in `tycoon/`) has its core
(machines, study, prototypes). Still to add: a fourth section for optional funding
- "Foerderungen" (a grant button on a cooldown that gives free Bargeld or Wissen)
and "Investoren" (spend Wissen / reputation for a big one-off Bargeld injection).

## Full app UI overhaul (not the Tycoon)

Redesign the general app UI - the tasks page, the navbar, the dialogs, and so on
(NOT the Tycoon page) - so the whole app looks more polished and professional.

## Untis as a second, separate portal

Add WebUntis (timetable / substitution plan) as its own portal integration, next to
the existing Logineo NRW / IServ portal (`portal/`). This should be a separate portal
type, not merged into the existing one, since Untis serves a different purpose
(timetable and substitutions, not homework) and most likely needs its own login flow.

## Later / bigger

These are meant to come at the very end, after the rest is done.

### Photo confirmation before a task pays out

Before a finished task grants its gold reward, require an AI photo confirmation: the
player takes a photo to prove they actually did the task, the AI checks it, and only
then is the gold paid out.

### Mobile phone app

Build a mobile (phone) app version of all of this.
