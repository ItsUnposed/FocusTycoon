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

## Tycoon: the placed-building popup says "gold/s" but it is Coins

When a commercial building is placed, the floating popup shows something like
"+X gold/s", but passive income is Coins now, not gold (see `_effect_text` in
`tycoon/ui/city_view.py`). Fix the wording so it says Coins everywhere it should.

## Tycoon: richer hover tooltip

Hovering a building (and a build-bar entry) should show a small tooltip with: what
it gives (residents or Coins per second), its current level, and how far it can
still be upgraded (for example "Level 3 / 5"). Right now hovering only highlights
the tile.

## Tycoon: a different look per upgrade level

Each upgrade should give the building a slightly different texture / look, and the
higher the level the more impressive ("krasser") it should look - so leveling up is
clearly visible on the building itself, not just as a number.

## Tycoon: a second business to build

Let the player build a separate "business" tycoon next to the city. It is also
chosen / paid for with gold, and the player can switch freely between the different
tycoons whenever they want. Important: the business does NOT use Coins - it has its
own separate currency.

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
