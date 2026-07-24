"""Business simulation for the electrical-engineering startup.

The simulation thread fills machine cycles and trickles Wissen from enrolled
study courses. The player buys machines (gold), collects them for Bargeld and
Wissen, upgrades machines and courses (Bargeld), enrolls in courses (gold) and
develops prototypes (Wissen + Bargeld). Every visible moment goes out on the
shared juice bus so the view can react.
"""

from __future__ import annotations

from .business_model import CourseInstance, MachineInstance
from .juice import JuiceEventBus


class BusinessBalance:
    # Simulation ticks per second (rendering runs on its own timer).
    TICK_RATE_HZ = 8


# ---------------------------------------------------------------- events

class MachineBought:
    def __init__(self, machine_id):
        self.machine_id = machine_id


class MachineCollected:
    def __init__(self, machine_id, bargeld, wissen):
        self.machine_id = machine_id
        self.bargeld = bargeld
        self.wissen = wissen


class MachineReady:
    def __init__(self, machine_id):
        self.machine_id = machine_id


class MachineUpgraded:
    def __init__(self, machine_id, new_level):
        self.machine_id = machine_id
        self.new_level = new_level


class CourseEnrolled:
    def __init__(self, course_id):
        self.course_id = course_id


class CourseUpgraded:
    def __init__(self, course_id, new_level):
        self.course_id = course_id
        self.new_level = new_level


class PrototypeDeveloped:
    def __init__(self, prototype_id):
        self.prototype_id = prototype_id


# ---------------------------------------------------------------- systems

class ProgressSystem:
    """Fills every machine's collect cycle each tick."""

    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        for instance in state.machines().values():
            if instance.advance(elapsed_seconds):
                bus.publish(MachineReady(instance.definition.id))


class StudySystem:
    """Trickles Wissen from every enrolled course each tick."""

    def tick(self, elapsed_seconds, state, bus: JuiceEventBus):
        gained = state.wissen_per_second() * elapsed_seconds
        if gained > 0:
            state.earn_wissen(gained)


# ---------------------------------------------------------------- actions

class BusinessActions:
    """The player actions: buy / collect / upgrade machines, enroll / upgrade
    courses, and develop prototypes."""

    # ---- machines ----

    def buy_machine(self, state, definition, bus: JuiceEventBus):
        if state.owns_machine(definition.id):
            return False
        if definition.unlock_prototype and not state.has_prototype(definition.unlock_prototype):
            return False
        if not state.gold().try_spend(definition.buy_cost_gold):
            return False
        state.add_machine(MachineInstance(definition))
        bus.publish(MachineBought(definition.id))
        return True

    def collect_machine(self, state, instance, bus: JuiceEventBus):
        bargeld, wissen = instance.collect()
        if bargeld <= 0 and wissen <= 0:
            return False
        # Developed prototypes boost the Bargeld yield.
        bargeld *= state.output_multiplier()
        state.earn_bargeld(bargeld)
        state.earn_wissen(wissen)
        bus.publish(MachineCollected(instance.definition.id, bargeld, wissen))
        return True

    def collect_all(self, state, bus: JuiceEventBus):
        collected = False
        for instance in state.machines().values():
            if self.collect_machine(state, instance, bus):
                collected = True
        return collected

    def upgrade_machine(self, state, instance, bus: JuiceEventBus):
        if not instance.can_upgrade():
            return False
        if not state.try_spend_bargeld(instance.upgrade_cost()):
            return False
        instance.upgrade()
        bus.publish(MachineUpgraded(instance.definition.id, instance.level()))
        return True

    # ---- courses ----

    def enroll_course(self, state, definition, bus: JuiceEventBus):
        if state.enrolled(definition.id):
            return False
        if not state.gold().try_spend(definition.enroll_cost_gold):
            return False
        state.add_course(CourseInstance(definition))
        bus.publish(CourseEnrolled(definition.id))
        return True

    def upgrade_course(self, state, instance, bus: JuiceEventBus):
        if not instance.can_upgrade():
            return False
        if not state.try_spend_bargeld(instance.upgrade_cost()):
            return False
        instance.upgrade()
        bus.publish(CourseUpgraded(instance.definition.id, instance.level()))
        return True

    # ---- prototypes ----

    def develop_prototype(self, state, definition, bus: JuiceEventBus):
        if state.has_prototype(definition.id):
            return False
        # Pay Wissen first, then Bargeld; refund the Wissen if Bargeld is short.
        if not state.try_spend_wissen(definition.cost_wissen):
            return False
        if not state.try_spend_bargeld(definition.cost_bargeld):
            state.earn_wissen(definition.cost_wissen)
            return False
        state.develop_prototype(definition)
        bus.publish(PrototypeDeveloped(definition.id))
        return True
