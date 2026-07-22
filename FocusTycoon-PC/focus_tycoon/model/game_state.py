"""Holds the whole task-side game state: gold and quests.

This is the central place for all task actions. Gold is the one shared balance:
finishing a task adds gold here, and the Tycoon map spends from the same balance.
"""

from __future__ import annotations

import threading

from ..service import calendar_import_service
from ..service.task_splitter import TaskSplitter
from .imported_homework import ImportedHomework
from .quest import Quest
from .task import Task

# Date format used for the homework due date inside the AI prompt.
_DUE_DATE_FORMAT = "%d.%m.%Y"


class GameState:
    def __init__(self, user_name, starting_gold, task_splitter=None):
        self._user_name = user_name
        self._gold = max(0, starting_gold)
        self._quests = []
        if task_splitter is None:
            task_splitter = TaskSplitter()
        self._task_splitter = task_splitter
        # Remembers which calendar events were already imported, to avoid duplicates.
        self._imported_event_keys = set()
        # Homework imported from a portal, stored by its external id.
        self._imported_homework = {}
        # Protects the gold value against changes from several threads at once.
        self._lock = threading.RLock()

    def add_quest(self, quest):
        """Add an already-built quest (used when loading a saved game)."""
        self._quests.append(quest)

    def process_new_task(self, input_text, description="", split_level=2,
                         estimated_total_minutes=0, quest_title=None):
        """Break a new task into steps and add it as a quest.

        The quest title stays short (for calendar/portal items we pass a short
        title separately); the longer text goes into the AI context only.
        """
        steps = self._task_splitter.break_down(
            input_text, description, split_level, estimated_total_minutes)
        if quest_title is None:
            quest_title = input_text
        quest = Quest(quest_title, split_level, steps)
        self._quests.append(quest)
        return quest

    def estimate_minutes(self, input_text, description):
        """Ask the AI for a rough total duration. Raises on failure."""
        return self._task_splitter.estimate_minutes(input_text, description)

    def import_from_calendar(self, events, split_level):
        """Import already-filtered calendar events as quests.

        Each event keeps a SHORT title (its summary); the full details are only
        given to the AI as extra context. Events that were already imported are
        skipped so we never create duplicate quests.
        """
        created_quests = []
        for event in events:
            if not event.has_summary():
                continue
            key = self._deduplication_key(event)
            if key in self._imported_event_keys:
                continue  # already imported - skip the duplicate
            context = calendar_import_service.build_ai_context(event)
            short_title = event.summary.strip()
            quest = self.process_new_task(
                short_title, context, split_level, 0, quest_title=short_title)
            self._imported_event_keys.add(key)
            created_quests.append(quest)
        return created_quests

    def _deduplication_key(self, event):
        """A stable key for an event, so we can detect duplicates."""
        if event.uid and event.uid.strip():
            return "uid:" + event.uid.strip()
        return f"sig:{event.summary}|{event.start}"

    # ---------- portal homework (import first, split later on demand) ----------

    def upsert_imported_homework(self, homework):
        """Insert or update an imported homework item (keyed by external id).

        We do NOT split or reward here. Splitting happens later, on demand, and
        only once. Returns True if the item was new, False if it already existed.
        """
        existing = self._imported_homework.get(homework.external_portal_id)
        if existing is not None:
            # Update the fields but keep the "already decomposed" flag.
            self._imported_homework[existing.external_portal_id] = ImportedHomework(
                homework.subject, homework.title, homework.due_date,
                existing.external_portal_id, existing.decomposed)
            return False
        self._imported_homework[homework.external_portal_id] = ImportedHomework(
            homework.subject, homework.title, homework.due_date,
            homework.external_portal_id, False)
        return True

    def get_imported_homework(self):
        return list(self._imported_homework.values())

    def find_imported_homework(self, external_portal_id):
        return self._imported_homework.get(external_portal_id)

    def decompose_imported_homework(self, external_portal_id, split_level):
        """Split an imported homework item into a quest - exactly once.

        Returns the new quest, or None if it is unknown or already split.
        """
        homework = self._imported_homework.get(external_portal_id)
        if homework is None or homework.decomposed:
            return None
        context = self._build_homework_description(homework)
        short_title = homework.title.strip()
        quest = self.process_new_task(
            short_title, context, split_level, 0, quest_title=short_title)
        self._imported_homework[external_portal_id] = homework.as_decomposed()
        return quest

    def _build_homework_description(self, homework):
        due = homework.due_date.strftime(_DUE_DATE_FORMAT)
        return (f"Homework for the subject {homework.subject}: {homework.title}."
                f" Due on {due}."
                " Create concrete steps to finish it in time.")

    # ---------- tasks ----------

    def complete_task(self, task_id):
        """Mark a stage as done and add its gold reward.

        Returns True on success, False if it was already done.
        """
        task = self.find_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if task.completed:
            return False
        task.completed = True
        self.add_gold(task.gold_reward)
        return True

    def recommend_next_task(self):
        """Recommend the smallest open step (smallest id on a tie) for a quick win."""
        open_steps = []
        for quest in self._quests:
            next_step = quest.find_next_open_stage()
            if next_step is not None:
                open_steps.append(next_step)
        if not open_steps:
            return None

        def sort_key(task):
            # We recommend the smallest step. A step with no estimated time has
            # an unknown length, so we treat it as very large here - it will only
            # be recommended if there is no step with a real (smaller) time.
            if task.estimated_minutes is None:
                minutes = 1000000000
            else:
                minutes = task.estimated_minutes
            return (minutes, task.id)

        return min(open_steps, key=sort_key)

    def move_stage_up(self, task_id):
        quest = self.find_quest_containing(task_id)
        if quest is None:
            return False
        return quest.move_stage_up(task_id)

    def move_stage_down(self, task_id):
        quest = self.find_quest_containing(task_id)
        if quest is None:
            return False
        return quest.move_stage_down(task_id)

    def find_quest_containing(self, task_id):
        for quest in self._quests:
            if quest.contains(task_id):
                return quest
        return None

    def find_task(self, task_id):
        for quest in self._quests:
            for stage in quest.get_stages():
                if stage.id == task_id:
                    return stage
        return None

    def get_all_tasks(self):
        all_tasks = []
        for quest in self._quests:
            all_tasks.extend(quest.get_stages())
        return all_tasks

    # ---------- gold (thread-safe) ----------

    def add_gold(self, amount):
        with self._lock:
            if amount > 0:
                self._gold += amount

    def spend_gold(self, amount):
        with self._lock:
            if amount <= 0:
                return True
            if self._gold < amount:
                return False
            self._gold -= amount
            return True

    def reset(self):
        with self._lock:
            self._gold = 0
            self._quests.clear()

    def get_user_name(self):
        return self._user_name

    def get_gold(self):
        with self._lock:
            return self._gold

    def get_quests(self):
        return list(self._quests)
