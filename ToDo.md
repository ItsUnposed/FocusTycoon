# TODO

Planned work for the Python/pygame version. The order below is not chronological
and does not imply priority - items can be picked up and worked on in any order.
The items near the very bottom ("later / bigger") are meant to come last.

## Done

Completed and shipped on the `ToDo` branch:

- [x] Rework the Tycoon into two games hosted on the Tycoon page: an isometric
      city builder and an electrical-engineering business.
- [x] Business tycoon core: study degrees (Bachelor, then Master) to unlock
      skills; level skills with Gold on a cooldown; skills gate machines,
      prototypes and products; BWL side skills give money bonuses / unlock
      automation.
- [x] Production chain: buy machines, develop prototypes, produce products into
      stock, sell stock for Bargeld; machines can break and be repaired.
- [x] Per-product automation (auto-produce / auto-sell) that can be bought and,
      once bought, toggled on (green) / off (orange).
- [x] Machine repairs are paid with Gold.
- [x] Bootstrap Gold -> Bargeld trade (unlimited, +50 per click).
- [x] Group the Education skills into collapsible themed sections.
- [x] Split the games into separate top-navbar entries (Aufgaben, Business, Stadt).
- [x] Make the business list scrollable (wheel, scrollbar, PgUp/PgDn/arrows).
- [x] Hidden debug panel (five quick clicks on the gold symbol) that adds Gold,
      Coins and Bargeld.

## todo-stadt

- [ ] Two buttons in the bottom-right corner (a left-arrow and a right-arrow).
      Clicking one rotates the whole city 90 degrees to the left or the right.

## todo-business

- [ ] GUI pass: replace the plain boxes with real illustrations / images for the
      machines, prototypes, products and skills. The game logic stays the same,
      only the look changes.
- [ ] Timeskip: add a debug-menu switch that turns off the upgrade / level-up
      wait time, so upgrades and skill level-ups finish instantly.
- [ ] More content (more machines, prototypes and products) plus a materials and
      inventory rework:
  - [ ] Remove the current odd product description text.
  - [ ] Add materials that are bought for Bargeld (buy any amount you can afford).
  - [ ] Add an inventory ("Lager") that shows which materials (and products) you
        own; you can also sell them back for 75% of their value.
  - [ ] Producing a product consumes the specific materials that product needs.
  - [ ] When auto-sell is off, produced products go into the inventory too.
  - [ ] Some products are needed to build other products (for example sensors and
        motors for a robot).

## Business tycoon: grants and investors

The electrical-engineering business tycoon (`business_*` in `tycoon/`) has its core
(education/skills, machines, prototypes, products, the daily gold->Bargeld trade).
Still to add: an optional funding section - "Foerderungen" (a grant button on a
cooldown that gives free Bargeld) and "Investoren" (a big one-off Bargeld injection
in exchange for something, e.g. a BWL skill / reputation).

## Business tycoon: keep expanding / subdividing content

Keep making everything more fine-grained and add more of it: more machines, more
products and prototypes, more skills, deeper tiers. The chain should feel rich and
long, closer to a real company. (The concrete next batch of content - materials, an
inventory and product-into-product recipes - is captured under todo-business above.)

## Business tycoon: balancing pass

Tune all the numbers (skill gold costs and cooldowns, machine/prototype/product
costs, material costs, sell prices, production times, break chances, automation
costs, the degree costs/times) so the whole chain paces well over many days of
tasks. Same for the city tycoon numbers.

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
