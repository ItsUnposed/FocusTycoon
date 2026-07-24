# TODO

Planned work for the Python/pygame version. The order below is not chronological
and does not imply priority - items can be picked up and worked on in any order.
The items near the very bottom ("later / bigger") are meant to come last.

## Tycoon overhaul

The Tycoon page (`tycoon/`) was reworked into an isometric city builder, but it is
still open for iteration: model, simulation, balancing and the pygame view
(`tycoon/ui/`) can all keep changing. The items below are the concrete next steps.

## Tycoon: group buildings in the build bar

Group the buildings in the build bar by category instead of showing them all in one
long row. Each group is a single entry; clicking it makes the group "fan out" (the
first building pops up above the group, then the rest spread out horizontally) so
the player can pick which building of that group they want to place. Clicking away
collapses the group again.

## Tycoon: a second, fully separate business

Add a second "business" tycoon that is COMPLETELY separate from the city - its own
world, its own state, its own currency (NOT the city's Coins). It is chosen / paid
for with gold.

The Tycoon page gets its own navbar (a navbar inside the Tycoon page, separate from
the app's main navbar) to switch between the different tycoons (city, business, and
any future ones). The player can switch back and forth freely at any time; each
tycoon keeps its own progress independently.

## German localization gaps

Some UI strings still show up in English while the app is in German mode. Find all of
them and translate them, so German mode is fully German.

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
