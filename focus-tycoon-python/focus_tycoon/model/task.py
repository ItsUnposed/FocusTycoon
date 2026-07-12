"""A single (micro-)task.

The gold reward is not a fixed number. It is calculated from the estimated
duration and the focus level, so that working with more focus is rewarded more.

Every task has a SHORT title (a heading of 1 to 5 words) and an optional longer
"detail" text. The heading stays short; all the longer explanation lives in the
detail field.
"""

from __future__ import annotations

import itertools
import threading

from ..util.java_compat import java_round

# How much gold one estimated minute of work is worth (before the focus bonus).
GOLD_PER_MINUTE = 10

# Every task gets a unique id. A lock keeps this safe if two threads create
# tasks at the same time.
_id_lock = threading.Lock()
_id_counter = itertools.count(1)


def create_next_task_id() -> int:
    with _id_lock:
        return next(_id_counter)


def clamp_energy_level(energy_level: int) -> int:
    """Keep the energy level inside the valid range of 1 to 3."""
    if energy_level < 1:
        return 1
    if energy_level > 3:
        return 3
    return energy_level


def focus_multiplier(energy_level: int) -> float:
    """Reward bonus per energy level.

    Level 1 (low energy) = normal reward.
    Level 2 (medium energy) = 20 percent more.
    Level 3 (high energy / hyperfocus) = 50 percent more.
    """
    level = clamp_energy_level(energy_level)
    if level == 2:
        return 1.2
    if level == 3:
        return 1.5
    return 1.0


def calculate_gold_reward(minutes: int, energy_level: int) -> int:
    """Central reward formula: gold = minutes * 10 * focus multiplier."""
    gold = (minutes * GOLD_PER_MINUTE) * focus_multiplier(energy_level)
    return java_round(gold)


class Task:
    def __init__(self, title: str, energy_level: int, estimated_minutes: int,
                 detail: str = "") -> None:
        self.id = create_next_task_id()
        self.title = title
        # A longer explanation of the step; the title stays a short heading.
        self.detail = detail
        self.energy_level = clamp_energy_level(energy_level)
        self.estimated_minutes = max(1, estimated_minutes)
        self.gold_reward = calculate_gold_reward(self.estimated_minutes, self.energy_level)
        self.completed = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Task):
            return False
        return other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id}, title='{self.title}', energy_level={self.energy_level}, "
            f"estimated_minutes={self.estimated_minutes}, gold_reward={self.gold_reward}, "
            f"completed={self.completed})"
        )
