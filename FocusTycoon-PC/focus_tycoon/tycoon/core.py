"""A fixed-rate scheduler for the simulation.

It is independent of the rendering: the pygame loop renders at its own frame rate
and only reads the TycoonState. This game loop ticks the simulation at a fixed
rate on a daemon thread.
"""

from __future__ import annotations

import threading
import time


class GameLoop:
    def __init__(self, tick_rate_hz, on_tick):
        self._tick_rate_hz = tick_rate_hz
        self._on_tick = on_tick
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        period = 1.0 / self._tick_rate_hz
        elapsed_per_tick = 1.0 / self._tick_rate_hz

        def run():
            next_time = time.monotonic()
            while not self._stop_event.is_set():
                try:
                    self._on_tick(elapsed_per_tick)
                except Exception as error:
                    print(f"Game loop tick failed: {error}")
                next_time += period
                sleep_time = next_time - time.monotonic()
                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)
                else:
                    next_time = time.monotonic()  # fell behind - resynchronise

        self._thread = threading.Thread(target=run, name="game-loop", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
