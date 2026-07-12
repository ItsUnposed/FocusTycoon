"""The colour palette and a few drawing helpers for the modern UI."""

from __future__ import annotations

import pygame

from ..util import ui_fonts

# ---- modern colour palette (as (r, g, b) tuples) ----
BG = (0x14, 0x18, 0x26)
BG_ALT = (0x11, 0x14, 0x1F)
NAVBAR = (0x1B, 0x20, 0x33)
PANEL = (0x1E, 0x24, 0x38)
CARD = (0x25, 0x2C, 0x44)
CARD_HI = (0x2E, 0x37, 0x57)
ACCENT = (0x6C, 0x8C, 0xFF)
SUCCESS = (0x2F, 0xBE, 0x8F)
GOLD = (0xF5, 0xC5, 0x42)
TEXT = (0xED, 0xEF, 0xF7)
MUTED = (0x8B, 0x92, 0xAB)
DISABLED = (0x3A, 0x40, 0x56)
STROKE = (0x32, 0x3A, 0x57)

RESET_BG = (0x3A, 0x22, 0x30)
RESET_FG = (0xF0, 0x8A, 0x8A)
DONE_CARD_BG = (0x1B, 0x3A, 0x31)
DONE_CARD_BORDER = (0x2C, 0x6B, 0x53)


def clamp_channel(value):
    if value < 0:
        return 0
    if value > 255:
        return 255
    return int(value)


def mix(color_a, color_b, ratio):
    """Blend two colours. ratio 0 = color_a, ratio 1 = color_b."""
    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0
    return (clamp_channel(color_a[0] + (color_b[0] - color_a[0]) * ratio),
            clamp_channel(color_a[1] + (color_b[1] - color_a[1]) * ratio),
            clamp_channel(color_a[2] + (color_b[2] - color_a[2]) * ratio))


def brighter(color, amount):
    return mix(color, (255, 255, 255), amount)


def darker(color, amount=0.2):
    return mix(color, (0, 0, 0), amount)


def rounded_rect(surface, rect, color, radius, border_color=None, border_width=0):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border_color is not None and border_width > 0:
        pygame.draw.rect(surface, border_color, rect, width=border_width, border_radius=radius)


def draw_text(surface, text, size, color, x, y, bold=False, italic=False, symbol=True):
    """Draw text at the top-left corner and return the rectangle it filled."""
    if symbol:
        font = ui_fonts.for_text(text, size, bold, italic)
    else:
        font = ui_fonts.base(size, bold, italic)
    rendered = font.render(text, True, color)
    surface.blit(rendered, (x, y))
    return rendered.get_rect(topleft=(x, y))


def draw_text_centered(surface, text, size, color, center_x, center_y,
                       bold=False, italic=False, symbol=True):
    if symbol:
        font = ui_fonts.for_text(text, size, bold, italic)
    else:
        font = ui_fonts.base(size, bold, italic)
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=(center_x, center_y))
    surface.blit(rendered, rect)
    return rect


def text_width(text, size, bold=False):
    return ui_fonts.for_text(text, size, bold).size(text)[0]
