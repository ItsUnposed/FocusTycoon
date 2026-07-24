"""Business tycoon data model: an electrical-engineering startup.

Three resources:
- Bargeld (cash): the firm's money. Machines earn it when collected; spent on
  upgrading machines and study courses.
- Wissen (knowledge): research. Study courses and R&D machines produce it; spent
  on developing prototypes.
- Gold (from finishing tasks, shared) is the startup capital: it buys machines
  and pays study tuition.

Machines fill a work cycle and are collected by the player. Courses run passively
and trickle Wissen while enrolled. Prototypes are one-time R&D that give a
permanent output boost and/or unlock a machine.

Everything here is plain data plus a BusinessState, touched by both the
simulation thread and the UI thread, so shared parts are guarded by locks.
"""

from __future__ import annotations

import math
import threading


def _grown_cost(base, growth, level):
    return math.ceil(base * (growth ** (level - 1)))


# ---------------------------------------------------------------- machines

class MachineDefinition:
    def __init__(self, machine_id, display_name, buy_cost_gold, base_bargeld,
                 base_wissen, cycle_seconds, max_level, base_upgrade_cost_bargeld,
                 upgrade_cost_growth, unlock_prototype, accent):
        self.id = machine_id
        self.display_name = display_name
        # Gold buys the machine (gold comes from finishing tasks).
        self.buy_cost_gold = buy_cost_gold
        # Bargeld and Wissen earned per completed cycle at level 1.
        self.base_bargeld = base_bargeld
        self.base_wissen = base_wissen
        self.cycle_seconds = cycle_seconds
        self.max_level = max_level
        # Upgrading a machine is paid in Bargeld.
        self.base_upgrade_cost_bargeld = base_upgrade_cost_bargeld
        self.upgrade_cost_growth = upgrade_cost_growth
        # A machine can be locked behind a developed prototype (or None).
        self.unlock_prototype = unlock_prototype
        self.accent = accent


class MachineInstance:
    def __init__(self, definition):
        self.definition = definition
        self._level = 1
        self._progress = 0.0
        self._ready = False
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def bargeld_per_cycle(self):
        with self._lock:
            return self.definition.base_bargeld * self._level

    def wissen_per_cycle(self):
        with self._lock:
            return self.definition.base_wissen * self._level

    def progress(self):
        with self._lock:
            return self._progress

    def is_ready(self):
        with self._lock:
            return self._ready

    def advance(self, elapsed_seconds):
        """Fill the cycle. Returns True if it JUST became ready this tick."""
        with self._lock:
            if self._ready:
                return False
            self._progress += elapsed_seconds / self.definition.cycle_seconds
            if self._progress >= 1.0:
                self._progress = 1.0
                self._ready = True
                return True
            return False

    def collect(self):
        """Bank a full cycle and restart it. Returns (bargeld, wissen), or (0, 0)."""
        with self._lock:
            if not self._ready:
                return 0.0, 0.0
            bargeld = self.definition.base_bargeld * self._level
            wissen = self.definition.base_wissen * self._level
            self._ready = False
            self._progress = 0.0
            return bargeld, wissen

    def can_upgrade(self):
        with self._lock:
            return self._level < self.definition.max_level

    def upgrade_cost(self):
        with self._lock:
            if self._level >= self.definition.max_level:
                return 0
            return _grown_cost(self.definition.base_upgrade_cost_bargeld,
                               self.definition.upgrade_cost_growth, self._level)

    def upgrade(self):
        with self._lock:
            if self._level < self.definition.max_level:
                self._level += 1

    def restore(self, level, progress, ready):
        with self._lock:
            self._level = max(1, min(self.definition.max_level, level))
            self._progress = max(0.0, min(1.0, progress))
            self._ready = bool(ready)


# ---------------------------------------------------------------- study courses

class CourseDefinition:
    def __init__(self, course_id, display_name, enroll_cost_gold,
                 base_wissen_per_second, max_level, base_upgrade_cost_bargeld,
                 upgrade_cost_growth, accent):
        self.id = course_id
        self.display_name = display_name
        # Gold tuition to enroll (paid once).
        self.enroll_cost_gold = enroll_cost_gold
        self.base_wissen_per_second = base_wissen_per_second
        self.max_level = max_level
        # Studying harder (upgrading the course) is paid in Bargeld.
        self.base_upgrade_cost_bargeld = base_upgrade_cost_bargeld
        self.upgrade_cost_growth = upgrade_cost_growth
        self.accent = accent


class CourseInstance:
    def __init__(self, definition):
        self.definition = definition
        self._level = 1
        self._lock = threading.RLock()

    def level(self):
        with self._lock:
            return self._level

    def wissen_per_second(self):
        with self._lock:
            return self.definition.base_wissen_per_second * self._level

    def can_upgrade(self):
        with self._lock:
            return self._level < self.definition.max_level

    def upgrade_cost(self):
        with self._lock:
            if self._level >= self.definition.max_level:
                return 0
            return _grown_cost(self.definition.base_upgrade_cost_bargeld,
                               self.definition.upgrade_cost_growth, self._level)

    def upgrade(self):
        with self._lock:
            if self._level < self.definition.max_level:
                self._level += 1

    def restore(self, level):
        with self._lock:
            self._level = max(1, min(self.definition.max_level, level))


# ---------------------------------------------------------------- prototypes

class PrototypeDefinition:
    def __init__(self, prototype_id, display_name, cost_wissen, cost_bargeld,
                 output_bonus, unlock_machine, accent):
        self.id = prototype_id
        self.display_name = display_name
        # Developing a prototype is paid in Wissen (and some Bargeld).
        self.cost_wissen = cost_wissen
        self.cost_bargeld = cost_bargeld
        # A permanent boost to every machine's Bargeld output (0.25 = +25%).
        self.output_bonus = output_bonus
        # Optionally unlocks a machine for buying (machine id, or None).
        self.unlock_machine = unlock_machine
        self.accent = accent


# ---------------------------------------------------------------- the state

class BusinessState:
    def __init__(self, gold):
        self._gold = gold
        self._bargeld = 0.0
        self._wissen = 0.0
        self._machines = {}         # machine id -> MachineInstance
        self._courses = {}          # course id -> CourseInstance
        self._prototypes = set()    # developed prototype ids
        self._output_bonus = 0.0    # summed bonus from developed prototypes
        self._lock = threading.RLock()

    def gold(self):
        return self._gold

    # ---------- Bargeld ----------

    def bargeld(self):
        with self._lock:
            return self._bargeld

    def earn_bargeld(self, amount):
        if amount <= 0:
            return
        with self._lock:
            self._bargeld += amount

    def try_spend_bargeld(self, amount):
        with self._lock:
            if self._bargeld < amount:
                return False
            self._bargeld -= amount
            return True

    # ---------- Wissen ----------

    def wissen(self):
        with self._lock:
            return self._wissen

    def earn_wissen(self, amount):
        if amount <= 0:
            return
        with self._lock:
            self._wissen += amount

    def try_spend_wissen(self, amount):
        with self._lock:
            if self._wissen < amount:
                return False
            self._wissen -= amount
            return True

    # ---------- machines ----------

    def owns_machine(self, machine_id):
        with self._lock:
            return machine_id in self._machines

    def machine(self, machine_id):
        with self._lock:
            return self._machines.get(machine_id)

    def machines(self):
        with self._lock:
            return dict(self._machines)

    def add_machine(self, instance):
        with self._lock:
            self._machines[instance.definition.id] = instance

    def output_multiplier(self):
        # Every developed prototype makes machines earn a bit more Bargeld.
        with self._lock:
            return 1.0 + self._output_bonus

    def bargeld_per_second(self):
        with self._lock:
            total = 0.0
            multiplier = 1.0 + self._output_bonus
            for machine in self._machines.values():
                total += machine.bargeld_per_cycle() * multiplier / machine.definition.cycle_seconds
            return total

    # ---------- courses ----------

    def enrolled(self, course_id):
        with self._lock:
            return course_id in self._courses

    def course(self, course_id):
        with self._lock:
            return self._courses.get(course_id)

    def courses(self):
        with self._lock:
            return dict(self._courses)

    def add_course(self, instance):
        with self._lock:
            self._courses[instance.definition.id] = instance

    def wissen_per_second(self):
        with self._lock:
            total = 0.0
            for course in self._courses.values():
                total += course.wissen_per_second()
            return total

    # ---------- prototypes ----------

    def has_prototype(self, prototype_id):
        with self._lock:
            return prototype_id in self._prototypes

    def prototype_ids(self):
        with self._lock:
            return set(self._prototypes)

    def develop_prototype(self, definition):
        with self._lock:
            if definition.id in self._prototypes:
                return
            self._prototypes.add(definition.id)
            self._output_bonus += definition.output_bonus

    # ---------- persistence helpers ----------

    def restore(self, bargeld, wissen):
        with self._lock:
            self._bargeld = max(0.0, bargeld)
            self._wissen = max(0.0, wissen)
