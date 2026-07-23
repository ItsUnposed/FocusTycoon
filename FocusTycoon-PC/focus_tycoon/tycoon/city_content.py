"""The building catalog and the starting city.

This is the "config file" of the city: every kind of building the player can
place, the population milestones, and the empty grid a new game begins with. It
is the only place to touch to add content - the engine never changes.

Balancing goal: with 1 to 2 finished tasks per day, growing the city into a full
metropolis should take a long time, so build and upgrade gold costs are high and
passive income is only a gentle trickle. Real progress comes from finishing tasks.
"""

from __future__ import annotations

from .city_model import (BuildingDefinition, CityState, CIVIC, COMMERCIAL,
                         RESIDENTIAL)

# The city is a fixed square grid of tiles.
GRID_COLUMNS = 6
GRID_ROWS = 6


class CityMilestone:
    """A one-time goal; condition(state) says whether it has been reached."""

    def __init__(self, milestone_id, description, condition):
        self.id = milestone_id
        self.description = description
        self.condition = condition


# ---------------------------------------------------------------- the catalog

# Each building: (id, name, category, build cost, base population, base income,
# max level, first-upgrade cost, upgrade growth, unlock population, floors,
# wall color, roof color). The catalog order is also the order shown in the
# build bar, so related buildings sit next to each other.
def build_catalog():
    return [
        # ---- residential: these add residents (population) ----
        BuildingDefinition("tent", "Tent", RESIDENTIAL, 40, 2, 0.0, 3,
                           30, 1.6, 0, 1, (214, 196, 150), (196, 120, 90)),
        BuildingDefinition("house", "House", RESIDENTIAL, 90, 4, 0.0, 5,
                           60, 1.7, 0, 1, (232, 214, 180), (176, 92, 74)),
        BuildingDefinition("apartment", "Apartment", RESIDENTIAL, 240, 12, 0.0, 5,
                           160, 1.8, 25, 3, (210, 200, 214), (120, 110, 150)),
        BuildingDefinition("tower", "Residential Tower", RESIDENTIAL, 700, 34, 0.0, 5,
                           420, 1.9, 120, 5, (180, 200, 220), (90, 120, 160)),
        # ---- commercial: these add a small passive gold income ----
        BuildingDefinition("stall", "Market Stall", COMMERCIAL, 70, 0, 0.4, 4,
                           50, 1.6, 0, 1, (230, 200, 120), (200, 120, 70)),
        BuildingDefinition("shop", "Shop", COMMERCIAL, 180, 0, 1.1, 5,
                           120, 1.75, 12, 2, (200, 220, 210), (80, 150, 140)),
        BuildingDefinition("office", "Office", COMMERCIAL, 480, 0, 3.0, 5,
                           300, 1.85, 45, 4, (170, 200, 220), (70, 110, 150)),
        BuildingDefinition("bank", "Bank", COMMERCIAL, 1200, 0, 8.0, 5,
                           700, 1.9, 140, 4, (220, 210, 170), (150, 130, 80)),
        # ---- civic: a park for a little population, a landmark for prestige ----
        BuildingDefinition("park", "Park", CIVIC, 120, 3, 0.0, 3,
                           90, 1.6, 8, 0, (120, 180, 110), (90, 160, 90)),
        BuildingDefinition("monument", "Monument", CIVIC, 2500, 20, 5.0, 3,
                           1500, 2.0, 220, 6, (222, 210, 180), (210, 180, 120)),
    ]


# ---------------------------------------------------------------- milestones

def _first_building(state):
    return state.building_count() >= 1


def _village(state):
    return state.total_population() >= 10


def _town(state):
    return state.total_population() >= 50


def _city(state):
    return state.total_population() >= 150


def _metropolis(state):
    return state.total_population() >= 300


def all_milestones():
    return [
        CityMilestone("first_building", "You placed your first building", _first_building),
        CityMilestone("village", "Your settlement became a village", _village),
        CityMilestone("town", "Your village grew into a town", _town),
        CityMilestone("city", "Your town became a city", _city),
        CityMilestone("metropolis", "Your city became a metropolis", _metropolis),
    ]


# ---------------------------------------------------------------- starting city

def build_initial_city(gold):
    """A brand-new city: the empty grid, ready for the first building."""
    return CityState(gold, GRID_COLUMNS, GRID_ROWS)
