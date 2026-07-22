"""The reference SoundEffectSink for pygame.

It builds short tones on the fly (no audio files needed): play_note plays one
pitched tone (the resource chimes), play_cue plays a short multi-note flourish for
the big moments. A master volume keeps everything gentle. Without an audio device
it just stays silent.
"""

from __future__ import annotations

import math
import struct

import pygame

from ..juice import SoundCue, SoundEffectSink

_SAMPLE_RATE = 44100
_MASTER_VOLUME = 0.32

# Hand-tuned flourishes per cue: (frequency, duration, sparkle, volume).
_CUES = {
    SoundCue.GENERATOR_FUELED: [
        (392, 0.09, False, 0.5), (587, 0.12, True, 0.5),
    ],
    SoundCue.GENERATOR_UPGRADED: [
        (523, 0.09, False, 0.5), (659, 0.09, False, 0.5), (784, 0.16, True, 0.55),
    ],
    SoundCue.RECIPE_COMPLETE: [
        (659, 0.08, True, 0.45), (880, 0.14, True, 0.5),
    ],
    SoundCue.SECTOR_UNLOCKED: [
        (523, 0.10, False, 0.5), (784, 0.10, False, 0.5), (1047, 0.22, True, 0.6),
    ],
    SoundCue.MILESTONE: [
        (523, 0.10, True, 0.55), (659, 0.10, True, 0.55),
        (784, 0.10, True, 0.55), (1047, 0.30, True, 0.65),
    ],
}


def _render_tone(frequency_hz, duration_seconds, sparkle, volume):
    """Build one short tone as raw 16-bit audio samples, entirely in code (no sound file)."""
    sample_count = int(_SAMPLE_RATE * duration_seconds)
    # A short fade in and out at the start/end of the tone, so it does not start or
    # stop with an audible "click".
    fade = max(1, sample_count // 8)
    buffer = bytearray(sample_count * 2)
    for i in range(sample_count):
        time_position = i / _SAMPLE_RATE
        # envelope ramps from 0 up to 1 near the start, stays at 1 in the middle, then
        # ramps back down to 0 near the end (the fade-in / fade-out mentioned above).
        envelope = min(1.0, min(i / fade, (sample_count - i) / fade))
        # A plain sine wave is the base tone.
        wave = math.sin(2 * math.pi * frequency_hz * time_position)
        if sparkle:
            # Mix in a quieter tone at double the frequency (one octave up) to give the
            # sound a brighter, "sparkly" character.
            wave = 0.7 * wave + 0.3 * math.sin(2 * math.pi * frequency_hz * 2 * time_position)
        # Scale the wave into the 16-bit sample range and apply volume settings.
        sample = int(wave * envelope * 32767 * volume * _MASTER_VOLUME)
        sample = max(-32768, min(32767, sample))
        struct.pack_into("<h", buffer, 2 * i, sample)
    return bytes(buffer)


class TonePlayer(SoundEffectSink):
    def __init__(self):
        self._available = pygame.mixer.get_init() is not None
        self._alive = True
        # Sound starts OFF by default. The player can turn it on with the sound
        # button in the navbar (see set_enabled below). Until then every play
        # call stays silent even if an audio device is available.
        self._enabled = False

    def is_enabled(self):
        return self._enabled

    def set_enabled(self, enabled):
        self._enabled = enabled

    def play_note(self, frequency_hz, duration_seconds, sparkle):
        self._play([(frequency_hz, duration_seconds, sparkle, 0.5)])

    def play_cue(self, cue):
        tones = _CUES.get(cue)
        if tones:
            self._play(tones)

    def _play(self, tones):
        # Stay silent when the sound is turned off, when we are shutting down,
        # or when there is no working audio device.
        if not self._enabled or not self._alive or not self._available:
            return
        try:
            # Join the tones one after another into a single buffer, so a "cue" made
            # of several notes plays as one short flourish instead of separate sounds.
            buffer = bytearray()
            for frequency, duration, sparkle, volume in tones:
                buffer += _render_tone(frequency, duration, sparkle, volume)
            sound = pygame.mixer.Sound(buffer=bytes(buffer))
            sound.play()
        except Exception:
            # no audio device / format problem: feedback is optional
            self._available = False

    def shutdown(self):
        self._alive = False
