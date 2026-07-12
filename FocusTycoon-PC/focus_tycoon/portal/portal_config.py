"""Loads the portal configuration.

Sources, by priority: 1) environment variables (they win), 2) a git-ignored file
~/.focustycoon/portal.env (KEY=VALUE lines, # comments).

Keys: PORTAL_ENCRYPTION_KEY (required), PORTAL_ISERV_URL, PORTAL_LOGINEO_URL, and
optionally PORTAL_<PORTAL>_USER/_PASS (demo).
"""

from __future__ import annotations

import os
from pathlib import Path

from .portal_type import PortalType

_ENV_KEYS = [
    "PORTAL_ENCRYPTION_KEY", "PORTAL_ISERV_URL", "PORTAL_LOGINEO_URL",
    "PORTAL_ISERV_USER", "PORTAL_ISERV_PASS",
    "PORTAL_LOGINEO_USER", "PORTAL_LOGINEO_PASS",
]


def default_file():
    return Path.home() / ".focustycoon" / "portal.env"


def load(file=None):
    if file is None:
        file = default_file()
    values = dict(_read_env_file(file))
    # Environment variables override values from the file.
    for key in _ENV_KEYS:
        environment_value = os.environ.get(key)
        if environment_value is not None and environment_value.strip():
            values[key] = environment_value
    return PortalConfig(values)


class PortalConfig:
    def __init__(self, values):
        self._values = values

    def get(self, key):
        return self._values.get(key)

    def encryption_key(self):
        key = self._values.get("PORTAL_ENCRYPTION_KEY")
        return key if key is not None else ""

    def has_encryption_key(self):
        return bool(self.encryption_key().strip())

    def school_url(self, portal_type):
        if portal_type == PortalType.ISERV:
            key = "PORTAL_ISERV_URL"
        else:
            key = "PORTAL_LOGINEO_URL"
        return self._values.get(key)

    def demo_user(self, portal_type):
        if portal_type == PortalType.ISERV:
            key = "PORTAL_ISERV_USER"
        else:
            key = "PORTAL_LOGINEO_USER"
        return self._values.get(key)

    def demo_password(self, portal_type):
        if portal_type == PortalType.ISERV:
            key = "PORTAL_ISERV_PASS"
        else:
            key = "PORTAL_LOGINEO_PASS"
        return self._values.get(key)


def _read_env_file(file):
    values = {}
    if file is None or not file.is_file():
        return values
    try:
        for raw_line in file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            equals_index = line.find("=")
            # No "=" (-1) or an empty key (0) means this line is not a valid
            # KEY=VALUE pair, so skip it.
            if equals_index <= 0:
                continue
            name = line[:equals_index].strip()
            value = _strip_quotes(line[equals_index + 1:].strip())
            values[name] = value
    except OSError as error:
        print(f"Portal config could not be read ({file}): {error}")
    return values


def _strip_quotes(value):
    # A value in the .env file may be wrapped in matching quotes, e.g. KEY="value".
    # If so, remove them; otherwise leave the value untouched.
    if len(value) < 2:
        return value
    wrapped_in_double_quotes = value.startswith('"') and value.endswith('"')
    wrapped_in_single_quotes = value.startswith("'") and value.endswith("'")
    if wrapped_in_double_quotes or wrapped_in_single_quotes:
        return value[1:-1]
    return value
