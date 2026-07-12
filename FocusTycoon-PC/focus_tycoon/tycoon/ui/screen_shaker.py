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
            # If a shake is already happening, only replace it with a stronger one so a
            # small event cannot cut a bigger shake short.
            if magnitude > self._magnitude:
                self._magnitude = magnitude
                self._remaining = duration_seconds

    def update(self, dt_seconds):
        """Call once per frame; counts down the shake timer and returns the current offset.

        The shake stays at full strength until its time runs out, then stops abruptly
        (there is no gradual fade)."""
        with self._lock:
            self._remaining -= dt_seconds
            # Once the shake's time is up, reset everything and report no offset.
            if self._remaining <= 0:
                self._magnitude = 0.0
                self._remaining = 0.0
                return 0, 0
            magnitude = self._magnitude
        # Pick a new random offset each frame, up to the current magnitude, so the
        # screen jitters back and forth instead of moving smoothly.
        offset_x = int(random.uniform(-1, 1) * magnitude)
        offset_y = int(random.uniform(-1, 1) * magnitude)
        return offset_x, offset_y
