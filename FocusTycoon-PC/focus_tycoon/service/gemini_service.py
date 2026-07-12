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
        has_time = _TIME_PATTERN.match(text) is not None
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
        if treat_as_single is None:
            treat_as_single = self.looks_like_a_fixed_appointment(raw_task_input)

        # "Do not split" or a detected fixed appointment: keep it as one task.
        if split_level == SPLIT_NONE or treat_as_single:
            minutes = estimated_total_minutes if estimated_total_minutes > 0 else 30
            reward_level = SPLIT_MEDIUM
            return [Task(raw_task_input, reward_level, minutes)]

        if not self.is_configured():
            raise RuntimeError(
                "No Gemini API key found. Please set GEMINI_API_KEY in your .env file.")

        prompt = self._build_breakdown_prompt(
            raw_task_input, description, split_level, estimated_total_minutes)
        answer_text = self._call_gemini_with_retry(prompt)
        return self._parse_steps(answer_text, split_level)

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
        level_instruction = self._level_instruction(split_level)

        context_block = ""
        if description is not None and description.strip():
            context_block = (
                "\nExtra context / details from the user (use this to make the steps more\n"
                "concrete and correct, but do not invent things that are not there):\n"
                f'"{description.strip()}"\n')

        estimate_block = ""
        if estimated_total_minutes > 0:
            estimate_block = (
                f"\nThe user thinks the whole task takes about {estimated_total_minutes} minutes.\n"
                'Spread the "estimated_minutes" of the steps so their sum is roughly this total\n'
                "(while staying inside the minute range given above for each step).\n")

        return (
            "You are a coach inside a gamified to-do app for students with ADHD.\n"
            "Your top rule: AVOID OVERWHELM. Match the size of the steps exactly to the\n"
            "chosen split level.\n\n"
            f"{level_instruction}\n\n"
            f'User task: "{raw_task_input}"\n'
            f"{context_block}{estimate_block}\n"
            "VERY IMPORTANT about splitting the REAL task:\n"
            "- Break down the ACTUAL content of the task, not a generic template.\n"
            "- If the task lists items, numbers, exercises or pages (for example\n"
            '  "Eva no. 1-10" or "read pages 12-20"), turn EACH item (or a small group)\n'
            "  into its own step. Never merge many items into a single step.\n\n"
            "FORMAT of each step:\n"
            '- "title": a SHORT heading of 1 to 5 words. No sentences, no details here.\n'
            '- "detail": one short sentence with the concrete instruction for this step.\n'
            '- "estimated_minutes": a whole number inside the range for the chosen level.\n\n"'
            "Answer with ONLY a valid JSON array, no other text and no markdown code block,\n"
            "in exactly this format:\n"
            '[{"title": "Short heading", "detail": "What to do here.", "estimated_minutes": 5}]\n')

    def _level_instruction(self, split_level):
        if split_level == SPLIT_FINE:
            return (
                "SPLIT LEVEL: FINE (split as much as possible).\n"
                "Create MANY tiny steps of 2 to 8 minutes each. Make one step per real\n"
                "sub-item of the task (for example one exercise number, one paragraph,\n"
                "one page). You may return up to 20 steps. Do NOT group several items\n"
                "into one step. Each step must be so small that it can never feel\n"
                "overwhelming.")
        if split_level == SPLIT_COARSE:
            return (
                "SPLIT LEVEL: COARSE (few large chunks).\n"
                "Create BIG, demanding chunks of 30 to 45 minutes each. Use 3 to 4 steps,\n"
                'each covering a large part of the task. "estimated_minutes" is between\n'
                "30 and 45.")
        # Medium is the balanced default.
        return (
            "SPLIT LEVEL: MEDIUM (balanced).\n"
            "Create solid standard steps of 10 to 15 minutes each. Use 3 to 5 steps.\n"
            '"estimated_minutes" is between 10 and 15.')

    def _build_estimate_prompt(self, raw_task_input, description):
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
        root = json.loads(response_body)
        candidates = root["candidates"]
        content = candidates[0]["content"]
        parts = content["parts"]
        return parts[0]["text"]

    def _parse_steps(self, answer_text, split_level):
        array = json.loads(answer_text.strip())
        # Fine mode may return many steps; medium/coarse only a few.
        reward_level = split_level if split_level in (SPLIT_FINE, SPLIT_MEDIUM, SPLIT_COARSE) else SPLIT_MEDIUM
        steps = []
        for item in array:
            title = self._shorten_title(str(item.get("title", "Step")))
            detail = str(item.get("detail", "")) if item.get("detail") is not None else ""
            minutes = self._read_int(item, 5, "estimated_minutes", "estimatedMinutes", "minutes")
            steps.append(Task(title, reward_level, minutes, detail))
        return steps

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
        for key in keys:
            value = obj.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
        return fallback
