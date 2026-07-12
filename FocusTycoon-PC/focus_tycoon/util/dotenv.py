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
        # First choice: a real environment variable always wins over the .env file.
        for key in keys:
            environment_value = os.environ.get(key)
            if environment_value is not None and environment_value.strip():
                return environment_value
        # Fall back to whatever was loaded from the .env file, if anything.
        for key in keys:
            file_value = self._values.get(key.lower())
            if file_value is not None and file_value.strip():
                return file_value
        return None


def load():
    """Load the nearest .env file (searching upward). Returns an empty DotEnv if none."""
    directory = Path.cwd()
    for _ in range(6):
        # "directory" becomes None once we have walked past the filesystem
        # root, so stop searching at that point.
        if directory is None:
            break
        candidate = directory / ".env"
        if candidate.is_file():
            return DotEnv(_read_env_file(candidate))
        # No .env file here, so move one folder up and try again.
        parent = directory.parent
        if parent == directory:
            # We are already at the filesystem root - there is no folder above it.
            directory = None
        else:
            directory = parent
    return DotEnv({})


def _read_env_file(file):
    values = {}
    try:
        for raw_line in file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            # Skip blank lines and comment lines (they start with "#").
            if not line or line.startswith("#"):
                continue
            equals_index = line.find("=")
            # A line without "=" (or one that starts with "=") is not a valid
            # KEY=VALUE pair, so ignore it.
            if equals_index <= 0:
                continue
            # Everything before "=" is the key, everything after is the value.
            name = line[:equals_index].strip().lower()
            value = _strip_quotes(line[equals_index + 1:].strip())
            values[name] = value
    except OSError as error:  # pragma: no cover
        print(f".env could not be read ({file}): {error}")
    return values


def _strip_quotes(value):
    """Remove a matching pair of quotes around the value, for example
    "hello" or 'hello' both become hello."""
    wrapped_in_double_quotes = (len(value) >= 2 and value.startswith('"')
                                 and value.endswith('"'))
    wrapped_in_single_quotes = (len(value) >= 2 and value.startswith("'")
                                 and value.endswith("'"))
    if wrapped_in_double_quotes or wrapped_in_single_quotes:
        return value[1:-1]
    return value
