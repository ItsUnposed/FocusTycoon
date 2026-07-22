"""The content registry and the starter content.

This is the "config file" of the neutral-fantasy world: resources, sectors
(floating islands), producers, recipes and milestones. It is the only place you
need to touch to add content - the engine never changes.

Balancing goal: with 1 to 2 finished tasks per day, fully maxing out the whole
Tycoon should take about 50 to 100 days. That is why producers run slowly on
their own, and upgrade / unlock gold costs are high - real progress comes from
finishing tasks (which grants gold and a Focus Surge).
"""

from __future__ import annotations

import math

from .economy import GoldAccount
from .model import (GeneratorDefinition, GeneratorInstance, MilestoneDefinition,
                    Position, RecipeDefinition, SectorDefinition, SectorInstance,
                    TycoonState, register_resource)

SECTOR_VERDANT = "verdant_isle"
SECTOR_CRYSTAL = "crystal_reef"
SECTOR_MIST = "mist_archipelago"
SECTOR_STAR = "star_citadel"

# ---- balance multipliers, all in one place so tuning is easy ----
# A global knob on how much gold every producer upgrade costs.
UPGRADE_GOLD_MULTIPLIER = 1.0
# Sector unlock costs are scaled up so a new island is a real goal.
UNLOCK_COST_MULTIPLIER = 10


class GameContentRegistry:
    def __init__(self):
        self._sectors = {}
        self._generators = {}
        self._recipes = {}
        self._milestones = {}

    def register_sector(self, definition):
        self._sectors[definition.id] = definition

    def register_generator(self, definition):
        self._generators[definition.id] = definition

    def register_recipe(self, definition):
        self._recipes[definition.id] = definition

    def register_milestone(self, definition):
        self._milestones[definition.id] = definition

    def sector(self, sector_id):
        return self._require(self._sectors, sector_id, "Sector")

    def generator(self, generator_id):
        return self._require(self._generators, generator_id, "Generator")

    def recipe(self, recipe_id):
        return self._require(self._recipes, recipe_id, "Recipe")

    def all_sectors(self):
        return list(self._sectors.values())

    def all_milestones(self):
        return list(self._milestones.values())

    def _require(self, entries, entry_id, kind):
        value = entries.get(entry_id)
        if value is None:
            raise ValueError(f"{kind} not registered: {entry_id}")
        return value


# ---------------------------------------------------------------- builders

# Every recipe here turns its inputs into exactly 1 output unit per unit of
# work, so output_per_unit is always fixed at 1.0.
def _make_recipe(recipe_id, name, inputs, output):
    return RecipeDefinition(recipe_id, name, inputs, output, 1.0)


# Helper so every raw-resource producer (one that turns nothing into a
# resource, recipe=None) is built the same way. `upgrade_cost_gold` is the gold
# cost of the FIRST upgrade; it grows per level by `growth`. 6 is the max level
# for these producers.
def _make_base_producer(generator_id, name, output, per_second, upgrade_cost_gold, growth):
    return GeneratorDefinition(
        generator_id, name, output, None, per_second,
        6, math.ceil(upgrade_cost_gold * UPGRADE_GOLD_MULTIPLIER), growth,
        output.glyph, output.accent)


# Same as _make_base_producer, but for refineries: the output resource comes
# from the recipe instead of being passed in directly, and refineries cap out
# at a lower max level (5) since they are worth more per level.
def _make_refinery(generator_id, name, recipe, per_second, upgrade_cost_gold, growth):
    output = recipe.output
    return GeneratorDefinition(
        generator_id, name, output, recipe, per_second,
        5, math.ceil(upgrade_cost_gold * UPGRADE_GOLD_MULTIPLIER), growth,
        output.glyph, output.accent)


def _total_resources(state):
    return sum(state.inventory().snapshot().values())


def _is_unlocked(state, sector_id):
    sector = state.sectors().get(sector_id)
    return sector is not None and sector.is_unlocked()


def register_all(registry):
    # ---- resources: tier 0 raw, tier 1 refined, tier 2 master ----
    raw_ore = register_resource("roherz", "Raw Ore", 0, "◆", (176, 141, 96))
    herbs = register_resource("kraeuter", "Herbs", 0, "❀", (104, 190, 112))
    raw_crystal = register_resource("rohkristall", "Raw Crystal", 0, "▲", (120, 176, 224))
    mist_dew = register_resource("nebeltau", "Mist Dew", 0, "✧", (168, 210, 220))

    crystal_bar = register_resource("kristallbarren", "Crystal Bar", 1, "❖", (150, 200, 255))
    elixir_essence = register_resource("elixier_essenz", "Elixir Essence", 1, "❥", (196, 132, 224))
    rune_dust = register_resource("runenstaub", "Rune Dust", 1, "✦", (214, 168, 255))
    aether_glass = register_resource("aetherglas", "Aether Glass", 1, "◈", (150, 232, 220))

    mana_stone = register_resource("manastein", "Mana Stone", 2, "★", (255, 214, 128))
    star_resin = register_resource("sternenharz", "Star Resin", 2, "✶", (255, 176, 208))

    # ---- sectors (floating islands) ----
    registry.register_sector(SectorDefinition(SECTOR_VERDANT, "Verdant Isle", "Where it all begins",
                                              Position(1, 1), 7, 4, 0, (74, 150, 96)))
    registry.register_sector(SectorDefinition(SECTOR_CRYSTAL, "Crystal Reef", "Crystals & runes",
                                              Position(9, 1), 7, 4, 140 * UNLOCK_COST_MULTIPLIER, (78, 140, 214)))
    registry.register_sector(SectorDefinition(SECTOR_MIST, "Mist Archipelago", "Mist & aether",
                                              Position(1, 6), 7, 4, 380 * UNLOCK_COST_MULTIPLIER, (86, 172, 178)))
    registry.register_sector(SectorDefinition(SECTOR_STAR, "Star Citadel", "Masterworks",
                                              Position(9, 6), 7, 4, 900 * UNLOCK_COST_MULTIPLIER, (190, 156, 82)))

    # ---- recipes (only used for the output resource now) ----
    smelt_ore = _make_recipe("smelt_ore", "Smelt Ore", {raw_ore: 3.0}, crystal_bar)
    brew_herb = _make_recipe("brew_herb", "Brew Herbs", {herbs: 3.0}, elixir_essence)
    grind_rune = _make_recipe("grind_rune", "Grind Runes", {raw_crystal: 3.0}, rune_dust)
    blow_glass = _make_recipe("blow_glass", "Blow Aether", {mist_dew: 3.0}, aether_glass)
    condense_mana = _make_recipe("condense_mana", "Condense Mana", {crystal_bar: 2.0, rune_dust: 2.0}, mana_stone)
    distill_star = _make_recipe("distill_star", "Distill Stars", {elixir_essence: 2.0, aether_glass: 2.0}, star_resin)
    for recipe in (smelt_ore, brew_herb, grind_rune, blow_glass, condense_mana, distill_star):
        registry.register_recipe(recipe)

    # ---- producers (per_second output, first-upgrade gold cost, cost growth) ----
    registry.register_generator(_make_base_producer("erzader", "Ore Vein", raw_ore, 0.9, 120, 1.7))
    registry.register_generator(_make_base_producer("kraeutergarten", "Herb Garden", herbs, 0.9, 120, 1.7))
    registry.register_generator(_make_base_producer("kristallbohrer", "Crystal Drill", raw_crystal, 0.75, 150, 1.7))
    registry.register_generator(_make_base_producer("nebelkondensator", "Mist Condenser", mist_dew, 0.7, 160, 1.7))

    registry.register_generator(_make_refinery("mana_schmelze", "Mana Forge", smelt_ore, 0.55, 180, 1.8))
    registry.register_generator(_make_refinery("alchemie_zirkel", "Alchemy Circle", brew_herb, 0.55, 180, 1.8))
    registry.register_generator(_make_refinery("runen_muehle", "Rune Mill", grind_rune, 0.5, 200, 1.8))
    registry.register_generator(_make_refinery("aether_veredler", "Aether Refiner", blow_glass, 0.5, 200, 1.8))

    registry.register_generator(_make_refinery("mana_kondensator", "Mana Condenser", condense_mana, 0.4, 320, 1.9))
    registry.register_generator(_make_refinery("sternen_destille", "Star Still", distill_star, 0.4, 320, 1.9))

    # ---- milestones ----
    # Reached as soon as the player holds any small amount of resources at
    # all - this is the very first goal a new player should hit.
    def first_output(state):
        return _total_resources(state) >= 15

    # Look through every sector's producers for one that has been upgraded
    # at least once (level 2 or higher).
    def first_upgrade(state):
        for sector in state.sectors().values():
            for generator in sector.generators():
                if generator.level() >= 2:
                    return True
        return False

    def crystal_unlocked(state):
        return _is_unlocked(state, SECTOR_CRYSTAL)

    # A bigger total-resources goal than first_output, marking real progress.
    def two_hundred_resources(state):
        return _total_resources(state) >= 200

    def mist_unlocked(state):
        return _is_unlocked(state, SECTOR_MIST)

    # Reached once the player has collected a handful of tier-2
    # (master-crafted) resources, regardless of which one.
    def first_masterwork(state):
        return state.inventory().amount_of(mana_stone) + state.inventory().amount_of(star_resin) >= 5

    def star_unlocked(state):
        return _is_unlocked(state, SECTOR_STAR)

    registry.register_milestone(MilestoneDefinition("first_output", "First resources produced", first_output))
    registry.register_milestone(MilestoneDefinition("first_upgrade", "First producer upgraded", first_upgrade))
    registry.register_milestone(MilestoneDefinition("crystal_unlocked", "Crystal Reef unlocked", crystal_unlocked))
    registry.register_milestone(MilestoneDefinition("two_hundred", "200 resources gathered", two_hundred_resources))
    registry.register_milestone(MilestoneDefinition("mist_unlocked", "Mist Archipelago unlocked", mist_unlocked))
    registry.register_milestone(MilestoneDefinition("first_masterwork", "First masterwork created", first_masterwork))
    registry.register_milestone(MilestoneDefinition("star_unlocked", "Star Citadel unlocked", star_unlocked))


def _make_generator(registry, generator_id, x, y):
    return GeneratorInstance(registry.generator(generator_id), Position(x, y))


def build_initial_state(registry, gold: GoldAccount):
    """Build the starting world: Verdant unlocked with its producers, others locked."""
    state = TycoonState(gold)

    verdant = SectorInstance(registry.sector(SECTOR_VERDANT), True)
    verdant.add_generator(_make_generator(registry, "erzader", 2, 2))
    verdant.add_generator(_make_generator(registry, "kraeutergarten", 4, 2))
    verdant.add_generator(_make_generator(registry, "mana_schmelze", 6, 2))
    state.add_sector(verdant)

    crystal = SectorInstance(registry.sector(SECTOR_CRYSTAL), False)
    crystal.add_generator(_make_generator(registry, "kristallbohrer", 10, 2))
    crystal.add_generator(_make_generator(registry, "runen_muehle", 12, 2))
    crystal.add_generator(_make_generator(registry, "alchemie_zirkel", 14, 2))
    state.add_sector(crystal)

    mist = SectorInstance(registry.sector(SECTOR_MIST), False)
    mist.add_generator(_make_generator(registry, "nebelkondensator", 2, 7))
    mist.add_generator(_make_generator(registry, "aether_veredler", 4, 7))
    state.add_sector(mist)

    star = SectorInstance(registry.sector(SECTOR_STAR), False)
    star.add_generator(_make_generator(registry, "mana_kondensator", 10, 7))
    star.add_generator(_make_generator(registry, "sternen_destille", 12, 7))
    state.add_sector(star)

    return state
