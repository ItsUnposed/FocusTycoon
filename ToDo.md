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
