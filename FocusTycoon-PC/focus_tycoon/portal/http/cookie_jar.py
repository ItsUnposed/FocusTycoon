"""A minimal cookie store.

On purpose this is not the standard cookie handler: that one drops cookies that
IServ / Moodle rely on. Behaviour: take each set-cookie header, use the part
before the first ';' as name=value, and only store it if both are non-empty and
the value is not 'deleted' (a deletion cookie must not overwrite a live session).
Every cookie name is accepted.
"""

from __future__ import annotations


class CookieJar:
    def __init__(self):
        self._cookies = {}

    def extract(self, set_cookie_values):
        for header in set_cookie_values or []:
            if not header:
                continue
            semicolon = header.find(";")
            pair = header[:semicolon] if semicolon >= 0 else header
            equals_index = pair.find("=")
            if equals_index < 0:
                continue
            name = pair[:equals_index].strip()
            value = pair[equals_index + 1:].strip()
            if not name or not value or value == "deleted":
                continue
            self._cookies[name] = value

    def __str__(self):
        # name=value pairs joined with "; " - ready for the Cookie header.
        return "; ".join(f"{name}={value}" for name, value in self._cookies.items())

    def has(self, name):
        return name in self._cookies

    def names(self):
        return self._cookies.keys()

    def size(self):
        return len(self._cookies)
