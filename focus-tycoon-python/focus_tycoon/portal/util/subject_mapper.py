"""Maps raw subject / course names to the app's subject keys."""

from __future__ import annotations

import re

_FALLBACK = "Other"

_COURSE_CODE = re.compile(r"^[A-Za-z0-9]+-([A-Za-z]{1,4})-")


def _fill(mapping, value, *keys):
    for key in keys:
        mapping[key] = value


# Prefix match on lower-cased raw text (the insertion order matters!).
_SUBJECT_MAP = {}
_fill(_SUBJECT_MAP, "Mathe", "mathematik", "math", "mathe")
_fill(_SUBJECT_MAP, "Deutsch", "deutsch", "german")
_fill(_SUBJECT_MAP, "Englisch", "englisch", "english")
_fill(_SUBJECT_MAP, "Physik", "physik", "physics")
_fill(_SUBJECT_MAP, "Bio", "biologie", "bio", "biology")
_fill(_SUBJECT_MAP, "Chemie", "chemie", "chemistry")
_fill(_SUBJECT_MAP, "Geschichte", "geschichte", "history")
_fill(_SUBJECT_MAP, "Erdkunde", "erdkunde", "geographie", "geografie", "geo")
_fill(_SUBJECT_MAP, "Sport", "sport", "pe")
_fill(_SUBJECT_MAP, "Musik", "musik", "music")
_fill(_SUBJECT_MAP, "Kunst", "kunst", "art")
_fill(_SUBJECT_MAP, "Informatik", "informatik", "info", "computer")

# Course code (upper case) -> subject key.
_CODE_MAP = {}
_fill(_CODE_MAP, "Mathe", "M", "MA")
_fill(_CODE_MAP, "Deutsch", "D")
_fill(_CODE_MAP, "Englisch", "E", "EN")
_fill(_CODE_MAP, "Bio", "BI", "BIO")
_fill(_CODE_MAP, "Chemie", "CH")
_fill(_CODE_MAP, "Physik", "PH", "PHY")
_fill(_CODE_MAP, "Erdkunde", "EK", "GEO")
_fill(_CODE_MAP, "Geschichte", "GE")
_fill(_CODE_MAP, "Informatik", "IF")
_fill(_CODE_MAP, "Kunst", "KU")
_fill(_CODE_MAP, "Sport", "SP")
_fill(_CODE_MAP, "Musik", "MU")
_fill(_CODE_MAP, "Sozialwissenschaften", "SW")
_fill(_CODE_MAP, "Philosophie", "PL")
_fill(_CODE_MAP, "Pädagogik", "PA")
_fill(_CODE_MAP, "Französisch", "F")
_fill(_CODE_MAP, "Latein", "L")
_fill(_CODE_MAP, "Spanisch", "SN")
_fill(_CODE_MAP, "Religion", "KR", "ER", "REL")
_fill(_CODE_MAP, "Politik", "PK")


def normalize_subject(raw):
    """Raw text -> a subject key via prefix match, otherwise a shortened raw / fallback."""
    if raw is None:
        return _FALLBACK
    lower = raw.lower().strip()
    if not lower:
        return _FALLBACK
    for key, value in _SUBJECT_MAP.items():
        if lower.startswith(key):
            return value
    trimmed = raw.strip()
    if not trimmed:
        return _FALLBACK
    return trimmed[:min(20, len(trimmed))]


def subject_from_course(shortname, fullname):
    """Moodle course -> subject: first the code in the shortname, else normalize_subject."""
    if shortname is not None:
        match = _COURSE_CODE.search(shortname)
        if match:
            code = match.group(1).upper()
            mapped = _CODE_MAP.get(code)
            if mapped is not None:
                return mapped
    if fullname is not None and fullname.strip():
        base = fullname
    elif shortname is not None and shortname.strip():
        base = shortname
    else:
        base = _FALLBACK
    return normalize_subject(base)
