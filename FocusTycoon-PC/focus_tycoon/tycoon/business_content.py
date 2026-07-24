"""The content of the electrical-engineering business tycoon.

Everything the player can interact with: machines to buy and collect, study
courses to enroll in, and prototypes to develop. This is the only file to touch
to add content - the engine never changes.

Balancing follows the rest of the app: gold (from finishing real tasks) is the
scarce startup capital that buys machines and pays tuition, while Bargeld and
Wissen are gentler streams the business produces itself.
"""

from __future__ import annotations

from .business_model import (BusinessState, CourseDefinition, MachineDefinition,
                            PrototypeDefinition)


class BusinessCatalog:
    def __init__(self, machines, courses, prototypes):
        self.machines = machines
        self.courses = courses
        self.prototypes = prototypes
        self.machine_by_id = {machine.id: machine for machine in machines}
        self.course_by_id = {course.id: course for course in courses}
        self.prototype_by_id = {prototype.id: prototype for prototype in prototypes}


# Machines: (id, name, buy gold, bargeld/cycle, wissen/cycle, cycle secs, max
# level, first-upgrade bargeld, upgrade growth, unlock prototype, accent).
def _machines():
    return [
        MachineDefinition("soldering", "Soldering Station", 60, 4, 0, 3.0, 5,
                         40, 1.6, None, (230, 180, 90)),
        MachineDefinition("psu", "Power Supply", 180, 14, 0, 6.0, 5,
                         130, 1.7, None, (210, 120, 90)),
        MachineDefinition("pcb", "PCB Printer", 500, 45, 1, 12.0, 5,
                         380, 1.8, None, (120, 170, 140)),
        MachineDefinition("lab", "Research Lab", 900, 0, 3, 10.0, 5,
                         500, 1.8, None, (150, 140, 210)),
        MachineDefinition("robot", "Assembly Robot", 2500, 220, 0, 20.0, 5,
                         1600, 1.9, "proto_automation", (130, 150, 180)),
        MachineDefinition("fab", "Chip Fab", 8000, 900, 4, 35.0, 5,
                         5000, 2.0, "proto_semiconductor", (120, 126, 150)),
    ]


# Courses: (id, name, enroll gold, wissen/second, max level, first-upgrade
# bargeld, upgrade growth, accent).
def _courses():
    return [
        CourseDefinition("basics", "Circuit Basics", 100, 0.5, 5, 80, 1.6, (120, 190, 150)),
        CourseDefinition("power", "Power Electronics", 400, 1.5, 5, 300, 1.7, (200, 160, 100)),
        CourseDefinition("micro", "Microelectronics", 1200, 4.0, 5, 900, 1.8, (160, 150, 220)),
    ]


# Prototypes: (id, name, cost wissen, cost bargeld, output bonus, unlocks
# machine id or None, accent).
def _prototypes():
    return [
        PrototypeDefinition("proto_efficiency", "Efficient Circuit", 40, 200, 0.25, None, (150, 210, 170)),
        PrototypeDefinition("proto_automation", "Automation Rig", 120, 800, 0.15, "robot", (150, 180, 220)),
        PrototypeDefinition("proto_semiconductor", "Semiconductor Process", 400, 3000, 0.25, "fab", (200, 170, 120)),
        PrototypeDefinition("proto_ai", "Smart Controller", 900, 8000, 0.5, None, (210, 150, 220)),
    ]


def build_catalog():
    return BusinessCatalog(_machines(), _courses(), _prototypes())


def build_initial_state(gold):
    """A brand-new startup: no machines, no courses, no prototypes, no money."""
    return BusinessState(gold)
