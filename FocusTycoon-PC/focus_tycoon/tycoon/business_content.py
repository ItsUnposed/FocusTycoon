"""Content of the electrical-engineering business tycoon: skills, machines,
prototypes and products, plus the starting state.

The chain: Skills gate Machines and Prototypes; a Prototype unlocks a Product;
producing a Product needs its Machine plus Bargeld for material; selling the
product gives Bargeld back (the margin is the profit).
"""

from __future__ import annotations

from .business_model import (BusinessState, MachineDefinition, PrototypeDefinition,
                            ProductDefinition, SkillDefinition)


class BusinessCatalog:
    def __init__(self, skills, machines, prototypes, products):
        self.skills = skills
        self.machines = machines
        self.prototypes = prototypes
        self.products = products
        self.skill_by_id = {s.id: s for s in skills}
        self.machine_by_id = {m.id: m for m in machines}
        self.prototype_by_id = {p.id: p for p in prototypes}
        self.product_by_id = {p.id: p for p in products}
        # Which prototype unlocks which product.
        self.product_prototype = {p.unlock_product: p.id for p in prototypes if p.unlock_product}


# Skills: (id, name, base gold cost, cost growth, base cooldown s, cooldown
# growth, max level, accent).
def _skills():
    return [
        SkillDefinition("grundlagen", "Basics", 60, 1.8, 20, 1.5, 5, (120, 190, 150)),
        SkillDefinition("elektronik", "Electronics", 150, 1.8, 40, 1.5, 5, (200, 160, 100)),
        SkillDefinition("fertigung", "Manufacturing", 300, 1.9, 60, 1.5, 5, (160, 150, 220)),
        SkillDefinition("automatisierung", "Automation", 600, 1.9, 90, 1.5, 5, (150, 180, 220)),
        SkillDefinition("bwl", "Business", 400, 1.8, 50, 1.5, 5, (210, 150, 220)),
    ]


# Machines: (id, name, buy bargeld, upgrade bargeld, upgrade growth, max level,
# required skill id, required skill level, break chance, repair bargeld, accent).
def _machines():
    return [
        MachineDefinition("loetstation", "Soldering Station", 120, 80, 1.6, 5,
                         "grundlagen", 1, 0.04, 40, (230, 180, 90)),
        MachineDefinition("pruefstand", "Test Bench", 400, 260, 1.7, 5,
                         "elektronik", 1, 0.05, 120, (210, 120, 90)),
        MachineDefinition("drucker", "PCB Printer", 1000, 600, 1.8, 5,
                         "fertigung", 1, 0.06, 300, (120, 170, 140)),
        MachineDefinition("roboter", "Assembly Robot", 3000, 1800, 1.9, 5,
                         "automatisierung", 2, 0.07, 800, (130, 150, 180)),
        MachineDefinition("fab", "Chip Fab", 9000, 5000, 2.0, 5,
                         "fertigung", 3, 0.08, 2500, (120, 126, 150)),
    ]


# Prototypes: (id, name, bargeld cost, required skill, required level, unlocked
# product id, accent).
def _prototypes():
    return [
        PrototypeDefinition("proto_kabel", "Cable Design", 150, "grundlagen", 1, "kabel", (150, 210, 170)),
        PrototypeDefinition("proto_netzteil", "Power Supply Design", 500, "elektronik", 2, "netzteil", (200, 170, 120)),
        PrototypeDefinition("proto_platine", "PCB Design", 1400, "fertigung", 2, "platine", (150, 180, 220)),
        PrototypeDefinition("proto_sensor", "Sensor Design", 4000, "automatisierung", 2, "sensor", (170, 150, 220)),
        PrototypeDefinition("proto_chip", "Chip Design", 12000, "fertigung", 3, "chip", (210, 150, 220)),
    ]


# Products: (id, name, required machine id, material bargeld, produce seconds,
# units per run, sell price bargeld, auto-produce cost, auto-sell cost, accent).
def _products():
    return [
        ProductDefinition("kabel", "Cable", "loetstation", 8, 3.0, 1, 20, 300, 200, (230, 180, 90)),
        ProductDefinition("netzteil", "Power Supply", "pruefstand", 30, 6.0, 1, 80, 900, 600, (210, 120, 90)),
        ProductDefinition("platine", "Circuit Board", "drucker", 90, 10.0, 1, 260, 2500, 1600, (120, 170, 140)),
        ProductDefinition("sensor", "Sensor", "roboter", 300, 15.0, 1, 900, 6000, 4000, (130, 150, 180)),
        ProductDefinition("chip", "Chip", "fab", 1000, 25.0, 1, 3200, 18000, 12000, (120, 126, 150)),
    ]


def build_catalog():
    return BusinessCatalog(_skills(), _machines(), _prototypes(), _products())


def build_initial_state(gold, catalog):
    return BusinessState(gold, catalog)
