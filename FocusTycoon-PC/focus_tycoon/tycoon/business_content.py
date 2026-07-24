"""The business catalog and the starting business tycoon.

This is the "config file" of the business tycoon: every business the player can
buy, in order. It is the only place to touch to add content - the engine never
changes.

Balancing goal, like the city: real progress comes from finishing tasks (which
grant the gold used to BUY businesses), so buy costs are high; Cash from the
businesses themselves is a gentler stream used for upgrades.
"""

from __future__ import annotations

from .business_model import BusinessDefinition, BusinessState


# Each business: (id, name, buy cost in gold, base profit in cash, cycle seconds,
# max level, first-upgrade cash cost, upgrade growth, cash-earned needed to
# unlock, accent colour). The order is also the order shown in the list.
def build_catalog():
    return [
        BusinessDefinition("lemonade", "Lemonade Stand", 50, 3, 3.0, 5,
                          40, 1.6, 0, (230, 200, 90)),
        BusinessDefinition("foodtruck", "Food Truck", 150, 12, 6.0, 5,
                          120, 1.7, 100, (210, 120, 90)),
        BusinessDefinition("cafe", "Cafe", 400, 40, 12.0, 5,
                          350, 1.8, 500, (170, 130, 110)),
        BusinessDefinition("workshop", "Workshop", 1000, 120, 20.0, 5,
                          900, 1.85, 2000, (130, 150, 170)),
        BusinessDefinition("factory", "Factory", 2500, 400, 35.0, 5,
                          2200, 1.9, 8000, (120, 126, 138)),
        BusinessDefinition("franchise", "Franchise", 6000, 1200, 60.0, 5,
                          5000, 2.0, 30000, (150, 200, 160)),
    ]


def build_initial_state(gold):
    """A brand-new business tycoon: no businesses owned yet, no cash."""
    return BusinessState(gold)
