"""Font selection with a symbol fallback (for pygame).

Fantasy glyphs (◆ ❀ ✦ ❖ ...) are missing in plain text fonts and would show up as
empty boxes. For text that contains such glyphs we pick a symbol-capable font
(Segoe UI Symbol and friends); for plain text we use the normal font. Font objects
are cached in a dictionary so we build each one only once.
"""

from __future__ import annotations

import pygame

_PRIMARY = "segoeui,dejavusans,arial"
# Symbol-capable candidates (Windows first, then widely supported fonts).
_SYMBOL = "segoeuisymbol,segoeuiemoji,arialunicodems,notosanssymbols2,dejavusans,segoeui"

# Cache of already-built fonts, keyed by (family, size, bold, italic).
_font_cache = {}


def _needs_symbol_font(text):
    # A rough rule: anything above the basic range is treated as a glyph.
    for character in text:
        if ord(character) > 0x2000:
            return True
    return False


def _get_font(family, size, bold, italic):
    key = (family, size, bold, italic)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    font = pygame.font.SysFont(family, size, bold=bold, italic=italic)
    _font_cache[key] = font
    return font


def base(size, bold=False, italic=False):
    """The normal font for plain text."""
    return _get_font(_PRIMARY, size, bold, italic)


def for_text(text, size, bold=False, italic=False):
    """A font that can show this text, including glyphs."""
    if _needs_symbol_font(text):
        family = _SYMBOL
    else:
        family = _PRIMARY
    return _get_font(family, size, bold, italic)
