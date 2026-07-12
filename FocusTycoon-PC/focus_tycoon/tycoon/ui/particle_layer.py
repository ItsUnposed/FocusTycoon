"""The reference ParticleEffectSink for pygame.

Each ParticleStyle has its own motion (dust drifts up, embers flicker, confetti
falls, starbursts fly out, rune rings snap outward) and uses the requested colour.
spawn_burst runs on the simulation thread, update / paint on the render thread, so
a lock keeps the particle list safe.
"""

from __future__ import annotations

import math
import random
import threading

import pygame

from ..juice import ParticleEffectRequest, ParticleStyle


class LiveParticle:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.life = 0.0
        self.max_life = 0.0
        self.size = 0.0
        self.gravity = 0.0
        self.spin = 0.0
        self.angle = 0.0
        self.color = (255, 255, 255)
        self.square = False


def _seed_radial(particle, origin_x, origin_y, min_speed, max_speed):
    angle = random.uniform(0, math.pi * 2)
    speed = random.uniform(min_speed, max_speed)
    particle.x = origin_x
    particle.y = origin_y
    particle.vx = math.cos(angle) * speed
    particle.vy = math.sin(angle) * speed


def _jitter_color(base_color):
    spread = 22
    return (max(0, min(255, base_color[0] + random.randint(-spread, spread))),
            max(0, min(255, base_color[1] + random.randint(-spread, spread))),
            max(0, min(255, base_color[2] + random.randint(-spread, spread))))


def _default_color(style):
    defaults = {
        ParticleStyle.MAGIC_DUST: (150, 190, 255),
        ParticleStyle.SPARKLE: (255, 224, 150),
        ParticleStyle.GLOW_PULSE: (190, 140, 255),
        ParticleStyle.EMBER: (255, 150, 90),
        ParticleStyle.RUNE_RING: (210, 170, 255),
        ParticleStyle.STARBURST: (255, 220, 140),
        ParticleStyle.CONFETTI: (255, 140, 200),
    }
    return defaults[style]


class ParticleLayer:
    def __init__(self, tile_size, fallback_width, fallback_height):
        self._tile_size = tile_size
        self._fallback_width = fallback_width
        self._fallback_height = fallback_height
        self._particles = []
        self._lock = threading.Lock()

    def spawn_burst(self, request: ParticleEffectRequest):
        tile_size = self._tile_size
        if request.position is not None:
            origin_x = request.position.grid_x * tile_size + tile_size / 2.0
            origin_y = request.position.grid_y * tile_size + tile_size / 2.0
        else:
            origin_x = self._fallback_width / 2.0
            origin_y = self._fallback_height / 2.0

        if request.color is not None:
            base_color = request.color
        else:
            base_color = _default_color(request.style)

        count = max(1, request.intensity)
        new_particles = []
        for _ in range(count):
            particle = LiveParticle()
            particle.color = _jitter_color(base_color)
            style = request.style
            if style == ParticleStyle.MAGIC_DUST:
                _seed_radial(particle, origin_x, origin_y, 15, 55)
                particle.vy -= 30
                particle.gravity = -12
                particle.size = random.uniform(3, 6)
                particle.max_life = random.uniform(0.5, 1.1)
            elif style == ParticleStyle.SPARKLE:
                _seed_radial(particle, origin_x, origin_y, 20, 70)
                particle.gravity = 40
                particle.size = random.uniform(2, 4)
                particle.max_life = random.uniform(0.25, 0.5)
            elif style == ParticleStyle.GLOW_PULSE:
                _seed_radial(particle, origin_x, origin_y, 8, 45)
                particle.gravity = 0
                particle.size = random.uniform(5, 9)
                particle.max_life = random.uniform(0.4, 0.8)
            elif style == ParticleStyle.EMBER:
                _seed_radial(particle, origin_x, origin_y, 10, 40)
                particle.vy -= 40
                particle.gravity = -20
                particle.size = random.uniform(2, 5)
                particle.max_life = random.uniform(0.5, 1.0)
            elif style == ParticleStyle.RUNE_RING:
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(90, 140)
                particle.x = origin_x
                particle.y = origin_y
                particle.vx = math.cos(angle) * speed
                particle.vy = math.sin(angle) * speed
                particle.size = random.uniform(3, 6)
                particle.max_life = random.uniform(0.4, 0.7)
                particle.square = True
                particle.spin = random.uniform(-6, 6)
            elif style == ParticleStyle.STARBURST:
                _seed_radial(particle, origin_x, origin_y, 80, 220)
                particle.gravity = 30
                particle.size = random.uniform(3, 7)
                particle.max_life = random.uniform(0.6, 1.2)
            elif style == ParticleStyle.CONFETTI:
                particle.x = origin_x + random.uniform(-self._fallback_width / 2.0, self._fallback_width / 2.0)
                particle.y = origin_y + random.uniform(-self._fallback_height / 2.0, -self._fallback_height / 6.0)
                particle.vx = random.uniform(-30, 30)
                particle.vy = random.uniform(20, 90)
                particle.gravity = 120
                particle.size = random.uniform(4, 8)
                particle.max_life = random.uniform(1.2, 2.2)
                particle.square = True
                particle.spin = random.uniform(-8, 8)
            particle.life = particle.max_life
            new_particles.append(particle)

        with self._lock:
            self._particles.extend(new_particles)

    def update(self, dt_seconds):
        with self._lock:
            for particle in self._particles:
                particle.x += particle.vx * dt_seconds
                particle.y += particle.vy * dt_seconds
                particle.vy += particle.gravity * dt_seconds
                particle.angle += particle.spin * dt_seconds
                particle.life -= dt_seconds
            self._particles = [p for p in self._particles if p.life > 0]

    def paint(self, surface, offset=(0, 0)):
        with self._lock:
            particles = list(self._particles)
        offset_x, offset_y = offset
        for particle in particles:
            if particle.max_life > 0:
                life_fraction = max(0.0, min(1.0, particle.life / particle.max_life))
            else:
                life_fraction = 0.0
            alpha = round(life_fraction * 235)
            if alpha <= 0:
                continue
            screen_x = particle.x + offset_x
            screen_y = particle.y + offset_y
            core_size = max(1, int(particle.size))
            glow_size = int(particle.size * 2.4)
            span = max(glow_size, core_size) * 2 + 4
            temp_surface = pygame.Surface((span, span), pygame.SRCALPHA)
            center = temp_surface.get_rect().center
            glow_color = (particle.color[0], particle.color[1], particle.color[2], round(alpha * 0.28))
            pygame.draw.circle(temp_surface, glow_color, center, glow_size)
            if particle.square:
                core = pygame.Surface((core_size * 2, core_size * 2), pygame.SRCALPHA)
                core.fill((particle.color[0], particle.color[1], particle.color[2], alpha))
                if abs(particle.angle) > 1e-3:
                    core = pygame.transform.rotate(core, -math.degrees(particle.angle))
                temp_surface.blit(core, core.get_rect(center=center))
            else:
                core_color = (particle.color[0], particle.color[1], particle.color[2], alpha)
                pygame.draw.circle(temp_surface, core_color, center, core_size)
            surface.blit(temp_surface, (int(screen_x - span / 2), int(screen_y - span / 2)))
