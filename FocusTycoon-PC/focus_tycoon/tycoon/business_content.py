"""Content of the electrical-engineering business tycoon: degrees, skills,
machines, prototypes and products, plus the starting state.

The chain: study a Degree (Bachelor, then Master) to unlock advanced Skills;
Skills gate Machines and Prototypes; a Prototype unlocks a Product; producing a
Product needs its Machine plus Bargeld for material; selling it gives Bargeld
back. The BWL (business) skills run alongside and give money bonuses / unlock
automation.
"""

from __future__ import annotations

from .business_model import (BusinessState, DegreeDefinition, MachineDefinition,
                            PrototypeDefinition, ProductDefinition, SkillDefinition)


class BusinessCatalog:
    def __init__(self, degrees, skills, machines, prototypes, products):
        self.degrees = degrees
        self.skills = skills
        self.machines = machines
        self.prototypes = prototypes
        self.products = products
        self.degree_by_id = {d.id: d for d in degrees}
        self.skill_by_id = {s.id: s for s in skills}
        self.machine_by_id = {m.id: m for m in machines}
        self.prototype_by_id = {p.id: p for p in prototypes}
        self.product_by_id = {p.id: p for p in products}
        self.product_prototype = {p.unlock_product: p.id for p in prototypes if p.unlock_product}


# Degrees: (id, name, gold cost, study seconds, required degree, accent).
def _degrees():
    return [
        DegreeDefinition("bachelor", "Electrical Engineering Bachelor", 1500, 300, None, (120, 190, 240)),
        DegreeDefinition("master", "Electrical Engineering Master", 4000, 600, "bachelor", (170, 150, 240)),
    ]


# Skills: (id, name, base gold, cost growth, base cooldown s, cooldown growth,
# max level, unlock degree or None, accent). Basics are open from the start;
# some skills need the Bachelor or Master first; BWL runs alongside.
def _skills():
    return [
        # --- electrical engineering basics (no degree needed) ---
        SkillDefinition("grundlagen", "Basics", 60, 1.8, 20, 1.5, 5, None, (120, 190, 150), group="basics"),
        SkillDefinition("schaltungstechnik", "Circuit Design", 120, 1.8, 30, 1.5, 5, None, (120, 180, 170), group="basics"),
        SkillDefinition("messtechnik", "Measurement", 180, 1.8, 35, 1.5, 5, None, (120, 170, 190), group="basics"),
        # --- unlocked by the Bachelor ---
        SkillDefinition("leistungselektronik", "Power Electronics", 300, 1.9, 60, 1.5, 5, "bachelor", (200, 160, 100), group="bachelor"),
        SkillDefinition("mikroelektronik", "Microelectronics", 400, 1.9, 70, 1.5, 5, "bachelor", (160, 150, 220), group="bachelor"),
        SkillDefinition("fertigung", "Manufacturing", 500, 1.9, 80, 1.5, 5, "bachelor", (170, 150, 130), group="bachelor"),
        # --- unlocked by the Master ---
        SkillDefinition("regelungstechnik", "Control Systems", 800, 2.0, 100, 1.5, 5, "master", (150, 180, 220), group="master"),
        SkillDefinition("halbleitertechnik", "Semiconductors", 1000, 2.0, 120, 1.5, 5, "master", (200, 170, 120), group="master"),
        SkillDefinition("automatisierung", "Automation", 900, 2.0, 110, 1.5, 5, "master", (150, 200, 180), group="master"),
        # --- BWL, on the side (no degree needed) ---
        SkillDefinition("bwl_grundlagen", "Business Basics", 200, 1.7, 40, 1.4, 5, None, (210, 150, 220), group="bwl"),
        SkillDefinition("marketing", "Marketing", 300, 1.7, 50, 1.4, 5, None, (220, 150, 190), group="bwl"),
        SkillDefinition("finanzen", "Finance", 300, 1.7, 50, 1.4, 5, None, (150, 210, 170), group="bwl"),
        SkillDefinition("management", "Management", 500, 1.8, 70, 1.4, 5, None, (200, 190, 150), group="bwl"),
    ]


# Machines: (id, name, buy bargeld, upgrade bargeld, upgrade growth, max level,
# required skill id, required skill level, break chance, repair bargeld, accent).
def _machines():
    return [
        MachineDefinition("loetstation", "Soldering Station", 120, 80, 1.6, 5,
                         "grundlagen", 1, 0.04, 40, (230, 180, 90)),
        MachineDefinition("pruefstand", "Test Bench", 400, 260, 1.7, 5,
                         "messtechnik", 1, 0.05, 120, (210, 120, 90)),
        MachineDefinition("drucker", "PCB Printer", 1000, 600, 1.8, 5,
                         "mikroelektronik", 1, 0.06, 300, (120, 170, 140)),
        MachineDefinition("roboter", "Assembly Robot", 3000, 1800, 1.9, 5,
                         "automatisierung", 1, 0.07, 800, (130, 150, 180)),
        MachineDefinition("fab", "Chip Fab", 9000, 5000, 2.0, 5,
                         "halbleitertechnik", 1, 0.08, 2500, (120, 126, 150)),
    ]


# Prototypes: (id, name, bargeld cost, required skill, required level, unlocked
# product id, accent).
def _prototypes():
    return [
        PrototypeDefinition("proto_kabel", "Cable Design", 150, "grundlagen", 1, "kabel", (150, 210, 170)),
        PrototypeDefinition("proto_netzteil", "Power Supply Design", 500, "schaltungstechnik", 2, "netzteil", (200, 170, 120)),
        PrototypeDefinition("proto_platine", "PCB Design", 1400, "leistungselektronik", 1, "platine", (150, 180, 220)),
        PrototypeDefinition("proto_sensor", "Sensor Design", 4000, "regelungstechnik", 1, "sensor", (170, 150, 220)),
        PrototypeDefinition("proto_chip", "Chip Design", 12000, "halbleitertechnik", 2, "chip", (210, 150, 220)),
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
    return BusinessCatalog(_degrees(), _skills(), _machines(), _prototypes(), _products())


def build_initial_state(gold, catalog):
    return BusinessState(gold, catalog)
