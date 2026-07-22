"""Talks to the Google Gemini API to break a big task into small steps.

Key rules of this version:

* There is NO offline fallback any more. If the API is not reachable, we retry
  for up to one minute and then raise a clear error. We never invent fake steps.
* The API key is never written in the code. It comes from the environment
  variable GEMINI_API_KEY or from a git-ignored ".env" file.
* Each step has a SHORT title (1 to 5 words) and a longer "detail" text.
* The "fine" level really splits the concrete task (for example every exercise
  number becomes its own step) instead of one generic block.

Split levels used across the app:
    0 = do not split (keep it as a single task)
    1 = fine   (many small concrete steps)
    2 = medium (a few balanced steps)
    3 = coarse (few large chunks)
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from ..model.task import Task
from ..util import dotenv

# Names we accept for the key, so people can use their preferred spelling.
API_KEY_NAMES = ("GEMINI_API_KEY", "GEMINI_KEY", "Gemini_API_Key")
MODEL_ENV_NAME = "GEMINI_MODEL"
DEFAULT_MODEL = "gemini-2.5-flash"
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

# How long we keep retrying a failing request before we give up (in seconds).
RETRY_BUDGET_SECONDS = 60
# How long we wait between two retries (in seconds).
RETRY_PAUSE_SECONDS = 4

# Split level meanings.
SPLIT_NONE = 0
SPLIT_FINE = 1
SPLIT_MEDIUM = 2
SPLIT_COARSE = 3

# Detects a clock time like "15:00" or "9.30" inside a text.
_TIME_PATTERN = re.compile(r".*\d{1,2}[:.]\d{2}.*", re.DOTALL)

# A private marker so we can tell "no value was passed" apart from "None was passed".
_NOT_GIVEN = object()


class GeminiService:
    def __init__(self, api_key=_NOT_GIVEN, model=_NOT_GIVEN, env=None) -> None:
        # With no arguments at all we load the key from the environment / .env file.
        # If the caller passes explicit values (even None) we use exactly those,
        # which lets tests force an "unconfigured" service.
        if env is None and api_key is _NOT_GIVEN and model is _NOT_GIVEN:
            env = dotenv.load()
        if env is not None:
            api_key = env.get_or_env(*API_KEY_NAMES)
            model = env.get_or_env(MODEL_ENV_NAME)
        if api_key is _NOT_GIVEN:
            api_key = None
        if model is _NOT_GIVEN:
            model = None

        self.api_key = api_key
        if model is not None and model.strip():
            self.model = model
        else:
            self.model = DEFAULT_MODEL

    def is_configured(self) -> bool:
        return self.api_key is not None and self.api_key.strip() != ""

    # ---------- deciding whether something is a fixed appointment ----------

    def looks_like_a_fixed_appointment(self, text) -> bool:
        """A rough check: does the text look like a fixed calendar appointment?

        Fixed appointments (a doctor's visit, a meeting at a set time) should not
        be split into steps.
        """
        if text is None or text.strip() == "":
            return False
        lower_text = text.lower().strip()
        # A clock time like "15:00" strongly suggests a fixed appointment.
        has_time = _TIME_PATTERN.match(text) is not None
        # Also check for German and English words that usually mean a fixed
        # appointment, since portal texts can be in either language.
        keywords = ("uhr", "termin", "meeting", "arzt", "verabredung", "geburtstag",
                    "appointment", "o'clock")
        has_keyword = False
        for keyword in keywords:
            if keyword in lower_text:
                has_keyword = True
                break
        return has_time or has_keyword

    # ---------- the main entry point ----------

    def break_down_task(self, raw_task_input, description="", split_level=SPLIT_MEDIUM,
                        estimated_total_minutes=0, treat_as_single=None):
        """Turn a raw task into a list of Task objects.

        Raises an error if the API is not configured or not reachable.
        """
        # If the caller did not say whether this is a fixed appointment,
        # guess it from the text itself.
        if treat_as_single is None:
            treat_as_single = self.looks_like_a_fixed_appointment(raw_task_input)

        # "Do not split" or a detected fixed appointment: keep it as one task.
        if split_level == SPLIT_NONE or treat_as_single:
            # Only give the task an estimated time if the user actually entered
            # one. If they left it empty (or 0), we do not invent a time - the
            # task simply has no estimated time (Task handles the reward).
            if estimated_total_minutes > 0:
                minutes = estimated_total_minutes
            else:
                minutes = None
            # Always use a medium reward level since there are no steps to base
            # a reward level on.
            reward_level = SPLIT_MEDIUM
            return [Task(raw_task_input, reward_level, minutes)]

        if not self.is_configured():
            raise RuntimeError(
                "No Gemini API key found. Please set GEMINI_API_KEY in your .env file.")

        prompt = self._build_breakdown_prompt(
            raw_task_input, description, split_level, estimated_total_minutes)
        answer_text = self._call_gemini_with_retry(prompt)
        return self._parse_steps(answer_text, split_level, estimated_total_minutes)

    def estimate_minutes(self, raw_task_input, description):
        """Ask the AI for a rough total duration (in minutes) for the whole task."""
        if not self.is_configured():
            raise RuntimeError(
                "No Gemini API key found. Please set GEMINI_API_KEY in your .env file.")
        prompt = self._build_estimate_prompt(raw_task_input, description)
        answer_text = self._call_gemini_with_retry(prompt)
        return self._parse_estimated_minutes(answer_text)

    # ---------- HTTP with automatic retry ----------

    def _call_gemini_with_retry(self, prompt):
        """Send the request, retrying for up to one minute if it fails."""
        deadline = time.monotonic() + RETRY_BUDGET_SECONDS
        last_error = None
        attempt = 0
        while True:
            attempt += 1
            try:
                return self._call_gemini_once(prompt)
            except Exception as error:  # noqa: BLE001 - we retry on any failure
                last_error = error
                if time.monotonic() >= deadline:
                    break
                time.sleep(RETRY_PAUSE_SECONDS)
        raise RuntimeError(
            "The AI could not be reached after retrying for one minute. "
            f"Please check your internet connection and API key. Last error: {last_error}")

    def _call_gemini_once(self, prompt):
        url = API_URL_TEMPLATE.format(model=self.model, key=self.api_key)
        request_body = self._build_request_body(prompt).encode("utf-8")
        request = urllib.request.Request(
            url, data=request_body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_text = response.read().decode("utf-8")
        except urllib.error.HTTPError as http_error:
            detail = http_error.read().decode("utf-8", "replace")
            raise IOError(f"Gemini API error (HTTP {http_error.code}): {detail}") from http_error
        return self._extract_answer_text(response_text)

    # ---------- prompts ----------

    def _build_breakdown_prompt(self, raw_task_input, description, split_level,
                                estimated_total_minutes):
        """Build the full text prompt we send to the Gemini API.

        This is plain text instructions for the AI, built up piece by piece:
        how much to split the task, the task itself, any extra context, whether
        to add per-step time estimates, and the exact JSON format we expect back.
        """
        level_instruction = self._level_instruction(split_level)

        # Only mention the extra description if the user actually gave one,
        # so the prompt does not confuse the AI with an empty context section.
        context_block = ""
        if description is not None and description.strip():
            context_block = (
                "\nExtra context / details from the user (use this to make the steps more\n"
                "concrete and correct, but do not invent things that are not there):\n"
                f'"{description.strip()}"\n')

        # The time rules and the exact JSON format depend on whether the user
        # gave a total time. We build both parts here so the two modes stay
        # clearly separated and easy to read.
        if estimated_total_minutes > 0:
            # The user entered a total, so every step gets an "estimated_minutes"
            # value and the parts must add up to exactly that total.
            time_block = (
                f"\nThe user says the WHOLE task takes about {estimated_total_minutes} minutes\n"
                'in total. Give every step an "estimated_minutes" value. Split this total\n'
                "across the steps by how much work each step really is: a bigger step gets\n"
                "more minutes, a small step gets fewer. Do NOT just divide the time evenly.\n"
                'The individual "estimated_minutes" values MUST add up to exactly\n'
                f"{estimated_total_minutes}.\n")
            format_block = (
                "FORMAT of each step:\n"
                '- "title": a SHORT heading of 1 to 5 words. No sentences, no details here.\n'
                '- "detail": one short sentence with the concrete instruction for this step.\n'
                '- "estimated_minutes": a whole number of minutes for this step (see the\n'
                "  time rule above).\n\n"
                "Answer with ONLY a valid JSON array, no other text and no markdown code block,\n"
                "in exactly this format:\n"
                '[{"title": "Short heading", "detail": "What to do here.", "estimated_minutes": 5}]\n')
        else:
            # The user left the time empty (or 0), so we must NOT invent any
            # time. The steps get no "estimated_minutes" field at all.
            time_block = (
                "\nThe user did NOT give a time estimate. Do NOT invent any time for the\n"
                'steps and do NOT include an "estimated_minutes" field at all.\n')
            format_block = (
                "FORMAT of each step:\n"
                '- "title": a SHORT heading of 1 to 5 words. No sentences, no details here.\n'
                '- "detail": one short sentence with the concrete instruction for this step.\n\n'
                "Answer with ONLY a valid JSON array, no other text and no markdown code block,\n"
                "in exactly this format:\n"
                '[{"title": "Short heading", "detail": "What to do here."}]\n')

        return (
            "You are a coach inside a gamified to-do app for students with ADHD.\n"
            "Your top rule: AVOID OVERWHELM. Match the size of the steps exactly to the\n"
            "chosen split level.\n\n"
            f"{level_instruction}\n\n"
            f'User task: "{raw_task_input}"\n'
            f"{context_block}{time_block}\n"
            "VERY IMPORTANT about splitting the REAL task:\n"
            "- Break down the ACTUAL content of the task, not a generic template.\n"
            "- If the task lists items, numbers, exercises or pages (for example\n"
            '  "Eva no. 1-10" or "read pages 12-20"), turn EACH item (or a small group)\n'
            "  into its own step. Never merge many items into a single step.\n\n"
            f"{format_block}")

    def _level_instruction(self, split_level):
        """Return the paragraph of prompt text describing the chosen split level.

        This only describes how many steps to make and how big each step should
        be. It does NOT talk about the "estimated_minutes" field, because whether
        steps get a time at all is decided separately in _build_breakdown_prompt.
        """
        if split_level == SPLIT_FINE:
            return (
                "SPLIT LEVEL: FINE (split as much as possible).\n"
                "Create MANY tiny steps, each only a few minutes of work (about 2 to 8\n"
                "minutes). Make one step per real sub-item of the task (for example one\n"
                "exercise number, one paragraph, one page). You may return up to 20 steps.\n"
                "Do NOT group several items into one step. Each step must be so small that\n"
                "it can never feel overwhelming.")
        if split_level == SPLIT_COARSE:
            return (
                "SPLIT LEVEL: COARSE (few large chunks).\n"
                "Create BIG, demanding chunks, each about 30 to 45 minutes of work. Use\n"
                "3 to 4 steps, each covering a large part of the task.")
        # Medium is the balanced default.
        return (
            "SPLIT LEVEL: MEDIUM (balanced).\n"
            "Create solid standard steps, each about 10 to 15 minutes of work. Use 3 to\n"
            "5 steps.")

    def _build_estimate_prompt(self, raw_task_input, description):
        """Build the prompt used by estimate_minutes to ask for a total duration."""
        context_block = ""
        if description is not None and description.strip():
            context_block = f'\nExtra context: "{description.strip()}"\n'
        return (
            "Estimate the realistic TOTAL duration (in minutes) for the following task of a\n"
            "student. Be realistic: not too optimistic, but not exaggerated either.\n"
            "Think about how long it truly takes, including reading and thinking time.\n\n"
            f'Task: "{raw_task_input}"\n'
            f"{context_block}\n"
            "Answer with ONLY a valid JSON object, no other text and no markdown code block,\n"
            "in exactly this format:\n"
            '{"estimated_minutes": 45}\n')

    def _build_request_body(self, prompt):
        # json.dumps safely escapes the prompt string for the JSON body.
        escaped_prompt = json.dumps(prompt)
        return (
            "{\n"
            '  "contents": [{"parts": [{"text": ' + escaped_prompt + "}]}],\n"
            '  "generationConfig": {"responseMimeType": "application/json"}\n'
            "}")

    # ---------- parsing the answer ----------

    def _extract_answer_text(self, response_body):
        """Dig the AI's actual text answer out of Gemini's response envelope.

        Gemini wraps its answer in a nested structure that looks like:
        {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
        We only ever ask for one answer, so we always read the first
        candidate and its first part.
        """
        root = json.loads(response_body)
        candidates = root["candidates"]
        content = candidates[0]["content"]
        parts = content["parts"]
        return parts[0]["text"]

    def _parse_steps(self, answer_text, split_level, estimated_total_minutes):
        # The prompt asks for a JSON array of step objects; answer_text
        # should already be exactly that.
        array = json.loads(answer_text.strip())
        # Fine mode may return many steps; medium/coarse only a few.
        reward_level = split_level if split_level in (SPLIT_FINE, SPLIT_MEDIUM, SPLIT_COARSE) else SPLIT_MEDIUM

        # First read the title and detail of every step, plus the raw minutes
        # the AI suggested (0 if it did not give any). We deal with the minutes
        # afterwards, because they need to be looked at all together.
        titles = []
        details = []
        raw_minutes = []
        for item in array:
            titles.append(self._shorten_title(str(item.get("title", "Step"))))
            if item.get("detail") is not None:
                details.append(str(item.get("detail", "")))
            else:
                details.append("")
            raw_minutes.append(
                self._read_int(item, 0, "estimated_minutes", "estimatedMinutes", "minutes"))

        # Decide the estimated time of each step:
        if estimated_total_minutes > 0:
            # The user gave a total, so every step gets a time and the parts have
            # to add up to exactly that total. The AI is not perfectly reliable,
            # so we adjust the numbers ourselves to guarantee the exact sum.
            minutes_per_step = self._distribute_minutes(raw_minutes, estimated_total_minutes)
        else:
            # No total was given, so no step gets an estimated time (None).
            minutes_per_step = []
            for _ in titles:
                minutes_per_step.append(None)

        steps = []
        for title, detail, minutes in zip(titles, details, minutes_per_step):
            steps.append(Task(title, reward_level, minutes, detail))
        return steps

    def _distribute_minutes(self, raw_values, total):
        """Turn the AI's rough per-step minutes into whole numbers that add up to
        exactly `total`.

        Steps that the AI thought were bigger (a higher raw value) get
        proportionally more minutes, so this is NOT a plain even split. Every
        step ends up with at least one minute.
        """
        count = len(raw_values)
        if count == 0:
            return []

        # If the total is smaller than the number of steps, there is no way to
        # give every step at least one minute AND still hit the total. In that
        # rare case we raise the total to the number of steps, so each step can
        # get its one minute.
        if total < count:
            total = count

        # Add up the raw values so we can work out each step's share. Only
        # positive values count as "weight"; a missing or zero value counts as 0.
        weight_sum = 0
        for value in raw_values:
            if value > 0:
                weight_sum += value

        # If the AI gave no usable numbers at all, fall back to an even split by
        # treating every step as equally heavy.
        if weight_sum <= 0:
            weights = []
            for _ in raw_values:
                weights.append(1)
            weight_sum = count
        else:
            weights = []
            for value in raw_values:
                if value > 0:
                    weights.append(value)
                else:
                    weights.append(0)

        # Give each step its share of the total, rounded down, but never less
        # than one minute.
        minutes = []
        for weight in weights:
            share = int((total * weight) / weight_sum)
            if share < 1:
                share = 1
            minutes.append(share)

        # Rounding down (and the "at least one minute" rule) means the parts may
        # not add up to the total yet. Hand out or take back single minutes, one
        # at a time from the largest step, until the sum matches exactly.
        difference = total - sum(minutes)
        while difference > 0:
            index = self._index_of_largest(minutes)
            minutes[index] += 1
            difference -= 1
        while difference < 0:
            index = self._index_of_largest_above_one(minutes)
            if index is None:
                # Every step is already at one minute; we cannot go any lower.
                break
            minutes[index] -= 1
            difference += 1
        return minutes

    def _index_of_largest(self, values):
        """Return the position of the biggest value in the list."""
        best_index = 0
        for index in range(1, len(values)):
            if values[index] > values[best_index]:
                best_index = index
        return best_index

    def _index_of_largest_above_one(self, values):
        """Return the position of the biggest value that is still above one,
        or None if every value is already one (or less)."""
        best_index = None
        for index in range(len(values)):
            if values[index] > 1:
                if best_index is None or values[index] > values[best_index]:
                    best_index = index
        return best_index

    def _shorten_title(self, title):
        """Safety net: keep the heading to at most 5 words."""
        words = title.strip().split()
        if len(words) <= 5:
            return title.strip()
        return " ".join(words[:5])

    def _parse_estimated_minutes(self, answer_text):
        obj = json.loads(answer_text.strip())
        return self._read_int(obj, 30, "estimated_minutes", "estimatedMinutes", "minutes")

    def _read_int(self, obj, fallback, *keys):
        # The AI might name the field differently between calls (snake_case
        # or camelCase), so try every known spelling before giving up.
        for key in keys:
            value = obj.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
        return fallback
