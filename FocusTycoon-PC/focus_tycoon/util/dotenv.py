"""A tiny reader for ".env" files, with no external dependencies.

It looks for a ".env" file in the current folder and its parent folders (up to 6
levels) and reads KEY=VALUE lines. Real environment variables always win. Keys are
compared without caring about upper/lower case.
"""

from __future__ import annotations

import os
from pathlib import Path


class DotEnv:
    def __init__(self, values):
        self._values = values

    def get_or_env(self, *keys):
        """Return the first matching value: a real environment variable wins,
        otherwise the value from the .env file. Returns None if nothing matches."""
        for key in keys:
            environment_value = os.environ.get(key)
            if environment_value is not None and environment_value.strip():
                return environment_value
        for key in keys:
            file_value = self._values.get(key.lower())
            if file_value is not None and file_value.strip():
                return file_value
        return None


def load():
    """Load the nearest .env file (searching upward). Returns an empty DotEnv if none."""
    directory = Path.cwd()
    for _ in range(6):
        if directory is None:
            break
        candidate = directory / ".env"
        if candidate.is_file():
            return DotEnv(_read_env_file(candidate))
        parent = directory.parent
        directory = parent if parent != directory else None
    return DotEnv({})


def _read_env_file(file):
    values = {}
    try:
        for raw_line in file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            equals_index = line.find("=")
            if equals_index <= 0:
                continue
            name = line[:equals_index].strip().lower()
            value = _strip_quotes(line[equals_index + 1:].strip())
            values[name] = value
    except OSError as error:  # pragma: no cover
        print(f".env could not be read ({file}): {error}")
    return values


def _strip_quotes(value):
    if len(value) >= 2 and ((value.startswith('"') and value.endswith('"'))
                            or (value.startswith("'") and value.endswith("'"))):
        return value[1:-1]
    return value
