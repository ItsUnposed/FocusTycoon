"""The "juice" pipeline: events -> bus -> director -> sinks.

Every dopamine moment is a JuiceEvent. The bus sends events to listeners; the
director turns them into calls on the three feedback sinks (particles, sound,
screen shake). Sinks can be no-ops (for headless / test use).
"""

from __future__ import annotations

import threading
import time
from enum import Enum

from ..util.java_compat import java_string_hashcode


# ---------------------------------------------------------------- Events

class JuiceEvent:
    """Base class for all dopamine-relevant events in the simulation."""


class GeneratorFueled(JuiceEvent):
    def __init__(self, generator_id, position, gold_spent):
        self.generator_id = generator_id
        self.position = position
        self.gold_spent = gold_spent


class GeneratorUpgraded(JuiceEvent):
    def __init__(self, generator_id, position, new_level):
        self.generator_id = generator_id
        self.position = position
        self.new_level = new_level


class ResourceProduced(JuiceEvent):
    def __init__(self, generator_id, position, resource, amount):
        self.generator_id = generator_id
        self.position = position
        self.resource = resource
        self.amount = amount


class RecipeCompleted(JuiceEvent):
    def __init__(self, generator_id, position, recipe, amount):
        self.generator_id = generator_id
        self.position = position
        self.recipe = recipe
        self.amount = amount


class MilestoneReached(JuiceEvent):
    def __init__(self, milestone):
        self.milestone = milestone


class SectorUnlocked(JuiceEvent):
    def __init__(self, sector_id, origin):
        self.sector_id = sector_id
        self.origin = origin


# ---------------------------------------------------------------- Bus

class JuiceEventBus:
    """A simple publish / subscribe pipeline (thread-safe)."""

    def __init__(self):
        self._listeners = []
        self._lock = threading.Lock()

    def subscribe(self, listener):
        with self._lock:
            self._listeners.append(listener)

    def publish(self, event):
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception as error:
                print(f"Juice listener failed for {event}: {error}")


# ---------------------------------------------------------------- Sinks

class ParticleStyle(Enum):
    MAGIC_DUST = 1    # soft drifting motes - just cheered
    SPARKLE = 2       # tiny sparks - a raw resource
    GLOW_PULSE = 3    # expanding halo - refined / recipe done
    EMBER = 4         # rising embers - hot producers
    RUNE_RING = 5     # rune ring snapping outward - an upgrade
    STARBURST = 6     # big radial starburst - a sector unlocked
    CONFETTI = 7      # full-screen celebration rain - a milestone


class ParticleEffectRequest:
    """A particle burst. position=None means 'in the middle of the screen'."""

    def __init__(self, position, style, intensity, color=None):
        self.position = position
        self.style = style
        self.intensity = intensity
        self.color = color


class ParticleEffectSink:
    def spawn_burst(self, request):
        raise NotImplementedError("spawn_burst() must be implemented by a subclass")


class SoundCue(Enum):
    GENERATOR_FUELED = 1
    GENERATOR_UPGRADED = 2
    RECIPE_COMPLETE = 3
    MILESTONE = 4
    SECTOR_UNLOCKED = 5


class SoundEffectSink:
    def play_cue(self, cue):
        raise NotImplementedError("play_cue() must be implemented by a subclass")

    def play_note(self, frequency_hz, duration_seconds, sparkle):
        raise NotImplementedError("play_note() must be implemented by a subclass")


class ScreenShakeSink:
    def shake(self, intensity, duration_seconds):
        raise NotImplementedError("shake() must be implemented by a subclass")


# No-op sinks (for headless / tests).

class _NoParticles(ParticleEffectSink):
    def spawn_burst(self, request):
        pass


class _NoSound(SoundEffectSink):
    def play_cue(self, cue):
        pass

    def play_note(self, frequency_hz, duration_seconds, sparkle):
        pass


class _NoShake(ScreenShakeSink):
    def shake(self, intensity, duration_seconds):
        pass


NO_PARTICLES = _NoParticles()
NO_SOUND = _NoSound()
NO_SHAKE = _NoShake()


# ---------------------------------------------------------------- Director

# C major pentatonic scale starting at C4.
_PENTATONIC = [261.63, 293.66, 329.63, 392.00, 440.00]
# Minimum gap between two resource notes, so a busy economy does not keep ringing.
_RESOURCE_NOTE_MIN_INTERVAL_SECONDS = 0.7


class JuiceDirector:
    """Turns JuiceEvents into sink calls."""

    def __init__(self, particles, sound, shake):
        self._particles = particles
        self._sound = sound
        self._shake = shake
        self._last_resource_note = 0.0

    def __call__(self, event):
        self.on_juice_event(event)

    def on_juice_event(self, event):
        if isinstance(event, GeneratorFueled):
            self._particles.spawn_burst(ParticleEffectRequest(
                event.position, ParticleStyle.MAGIC_DUST, 22))
            self._sound.play_cue(SoundCue.GENERATOR_FUELED)
            self._shake.shake(0.4, 0.16)

        elif isinstance(event, ResourceProduced):
            resource = event.resource
            self._particles.spawn_burst(ParticleEffectRequest(
                event.position, self._style_for_tier(resource.tier), 7, resource.accent))
            self._play_throttled_note(self._note_for(resource), 0.11, resource.tier >= 1)

        elif isinstance(event, RecipeCompleted):
            resource = event.recipe.output
            self._particles.spawn_burst(ParticleEffectRequest(
                event.position, ParticleStyle.GLOW_PULSE, 12, resource.accent))
            self._play_throttled_note(self._note_for(resource), 0.16, True)

        elif isinstance(event, GeneratorUpgraded):
            self._particles.spawn_burst(ParticleEffectRequest(
                event.position, ParticleStyle.RUNE_RING, 26))
            self._sound.play_cue(SoundCue.GENERATOR_UPGRADED)
            self._shake.shake(0.55, 0.22)

        elif isinstance(event, SectorUnlocked):
            self._particles.spawn_burst(ParticleEffectRequest(
                event.origin, ParticleStyle.STARBURST, 46))
            self._sound.play_cue(SoundCue.SECTOR_UNLOCKED)
            self._shake.shake(0.85, 0.32)

        elif isinstance(event, MilestoneReached):
            self._particles.spawn_burst(ParticleEffectRequest(
                None, ParticleStyle.CONFETTI, 64))
            self._sound.play_cue(SoundCue.MILESTONE)
            self._shake.shake(1.0, 0.4)

    def _play_throttled_note(self, frequency_hz, duration_seconds, sparkle):
        now = time.monotonic()
        if now - self._last_resource_note < _RESOURCE_NOTE_MIN_INTERVAL_SECONDS:
            return
        self._last_resource_note = now
        self._sound.play_note(frequency_hz, duration_seconds, sparkle)

    def _style_for_tier(self, tier):
        # Raw resources sparkle; refined resources pulse.
        if tier == 0:
            return ParticleStyle.SPARKLE
        return ParticleStyle.GLOW_PULSE

    def _note_for(self, resource):
        # Each resource gets a fixed note; higher tiers move up an octave.
        index = java_string_hashcode(resource.id) % len(_PENTATONIC)
        octave = 2 ** min(2, resource.tier)
        return _PENTATONIC[index] * octave
