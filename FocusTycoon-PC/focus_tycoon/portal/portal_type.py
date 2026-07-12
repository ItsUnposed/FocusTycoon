"""The supported school portals.

wire = the stable id used for storage / config, display_name = the text shown in
the UI and log messages.
"""

from __future__ import annotations

import enum


class PortalType(enum.Enum):
    ISERV = ("iserv", "IServ")
    LOGINEO_NRW = ("logineo_nrw", "Logineo NRW")

    def __init__(self, wire, display_name):
        self.wire = wire
        self.display_name = display_name


def from_wire(text):
    for portal in PortalType:
        if portal.wire.lower() == (text or "").lower():
            return portal
    raise ValueError(f"Unknown portal type: {text}")
