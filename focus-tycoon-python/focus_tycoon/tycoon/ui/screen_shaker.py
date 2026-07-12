"""The reference ScreenShakeSink.

It jitters a small pixel offset that MapView applies before drawing, so a big
event (an upgrade, an unlock) gives a short screen shake.
"""

from __future__ import annotations

import random
import threading

from ..juice import ScreenShakeSink


class ScreenShaker(ScreenShakeSink):
    def __init__(self):
        self._magnitude = 0.0
        self._remaining = 0.0
        self._lock = threading.Lock()

    def shake(self, intensity, duration_seconds):
        magnitude = intensity * 14
        with self._lock:
            if magnitude > self._magnitude:
                self._magnitude = magnitude
                self._remaining = duration_seconds

    def update(self, dt_seconds):
        """Call once per frame; it fades the shake out and returns the offset."""
        with self._lock:
            self._remaining -= dt_seconds
            if self._remaining <= 0:
                self._magnitude = 0.0
                self._remaining = 0.0
                return 0, 0
            magnitude = self._magnitude
        offset_x = int(random.uniform(-1, 1) * magnitude)
        offset_y = int(random.uniform(-1, 1) * magnitude)
        return offset_x, offset_y
