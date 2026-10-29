"""Particle effects and screen shake.

Particles live in screen pixels. Each one moves, falls under its own
gravity and shrinks away as its life runs out. Sizes and speeds are for
the 960x640 design size and are multiplied by the window's scale.
"""

import math
import random

import pygame

SPARK = "spark"        # round glowing dot, used for bursts
CHUNK = "chunk"        # small spinning square, used for breaking ice
CONFETTI = "confetti"  # flat fluttering rectangle, used on the win screen


class Particle:
    """One particle on screen."""

    def __init__(self, x, y, vx, vy, life, colour, size, gravity, kind):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.colour = colour
        self.size = size
        self.gravity = gravity
        self.kind = kind
        self.angle = random.uniform(0, math.tau)
        self.spin = random.uniform(-8, 8)

    def update(self, dt):
        """Move the particle by its velocity, apply gravity and age it by dt seconds."""
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt
        self.life -= dt

    def draw(self, screen):
        """Draw the particle, shrinking and fading as it gets older."""
        fraction = max(self.life / self.max_life, 0)
        if self.kind == SPARK:
            radius = max(1, round(self.size * fraction))
            pygame.draw.circle(screen, self.colour, (self.x, self.y), radius)
            if radius >= 3:
                # A bright centre makes the spark look like it glows.
                pygame.draw.circle(screen, (255, 255, 255), (self.x, self.y), radius // 2)
        else:
            # A spinning square (chunk) or a fluttering strip (confetti).
            width = self.size
            height = self.size if self.kind == CHUNK else self.size * 0.45
            dx, dy = math.cos(self.angle), math.sin(self.angle)
            points = [
                (self.x + dx * sx * width - dy * sy * height, self.y + dy * sx * width + dx * sy * height)
                for sx, sy in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))
            ]
            pygame.draw.polygon(screen, self.colour, points)


class Effects:
    """Keeps track of every live particle and the current screen shake."""

    def __init__(self, scale=1.0):
        self.scale = scale
        self.particles = []
        self.shake_time = 0.0
        self.shake_length = 0.0
        self.shake_strength = 0.0

    def clear(self):
        """Remove every particle and stop any shake (used when a level restarts)."""
        self.particles = []
        self.shake_time = 0.0

    def burst(self, position, colour, count=22, speed=(60, 190), life=(0.35, 0.8), size=(2, 5)):
        """Throw sparks out in every direction from a screen position."""
        x, y = position
        s = self.scale
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            power = random.uniform(*speed) * s
            self.particles.append(Particle(
                x, y, math.cos(angle) * power, math.sin(angle) * power - 40 * s,
                random.uniform(*life), colour, random.uniform(*size) * s, 160 * s, SPARK,
            ))

    def chunks(self, position, colour, count=16):
        """Throw heavy chunks that tumble and fall, like breaking ice."""
        x, y = position
        s = self.scale
        for _ in range(count):
            self.particles.append(Particle(
                x + random.uniform(-14, 14) * s, y + random.uniform(-6, 6) * s,
                random.uniform(-110, 110) * s, random.uniform(-220, -60) * s,
                random.uniform(0.6, 1.1), colour, random.uniform(5, 10) * s, 900 * s, CHUNK,
            ))

    def confetti(self, screen_width, colours, count=3):
        """Drop a few pieces of confetti from the top of the screen."""
        s = self.scale
        for _ in range(count):
            self.particles.append(Particle(
                random.uniform(0, screen_width), -10 * s,
                random.uniform(-40, 40) * s, random.uniform(60, 140) * s,
                random.uniform(3.0, 5.0), random.choice(colours), random.uniform(8, 13) * s, 25 * s, CONFETTI,
            ))

    def shake(self, strength, length):
        """Start shaking the screen for a short time."""
        self.shake_strength = strength * self.scale
        self.shake_length = length
        self.shake_time = length

    def offset(self):
        """How far to move the board this frame because of screen shake."""
        if self.shake_time <= 0:
            return (0, 0)
        strength = self.shake_strength * self.shake_time / self.shake_length
        return (random.uniform(-strength, strength), random.uniform(-strength, strength))

    def update(self, dt):
        """Advance the screen shake and every particle, dropping the dead ones."""
        self.shake_time = max(0.0, self.shake_time - dt)
        for particle in self.particles:
            particle.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]

    def draw(self, screen):
        """Draw every live particle."""
        for particle in self.particles:
            particle.draw(screen)
