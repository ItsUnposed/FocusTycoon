"""Two small helpers that copy Java behaviour.

The gold reward uses Java's rounding (round half up), and the resource sound in
the Tycoon maps each resource id to a note using Java's String.hashCode(). These
two functions keep that behaviour identical to the original Java app.
"""

from __future__ import annotations

import math

# A mask that keeps only the lowest 32 bits of a number.
_UNSIGNED_32_BIT_MASK = 0xFFFFFFFF


def java_string_hashcode(text):
    """Copy of java.lang.String.hashCode() (a signed 32-bit integer)."""
    if text is None:
        return 0
    hash_value = 0
    for character in text:
        # Java integers wrap around ("overflow") at 32 bits, so mask the
        # running total down to 32 bits after every step to copy that behaviour.
        hash_value = (31 * hash_value + ord(character)) & _UNSIGNED_32_BIT_MASK
    if hash_value >= 0x80000000:
        # The top bit is set, which in Java's signed 32-bit integers means the
        # value is negative. Convert it into the matching negative number.
        hash_value -= 0x100000000
    return hash_value


def java_round(value):
    """Copy of Math.round(double) = floor(x + 0.5) (round half up)."""
    return math.floor(value + 0.5)
