"""Small hand-drawn icons: padlocks for gates, and keys.

Each icon is drawn at 4x detail and then smoothly shrunk to the size
needed, which gives soft, clean edges at any screen scale. The result is
kept and reused, so the shapes aren't redrawn every frame.
"""

import pygame

OUTLINE = (30, 26, 40)
KEYHOLE = (30, 26, 40)
DETAIL = 4  # draw this many times bigger, then shrink

PADLOCK_SIZE = (28, 40)
KEY_SIZE = (46, 24)

_cache = {}


def _shade(colour, factor):
    """Multiply a colour by factor, kept within 0-255."""
    return tuple(max(0, min(255, int(channel * factor))) for channel in colour)


def _finish(surface, base_size, scale):
    """Shrink a 4x drawing down to base_size times the screen scale."""
    size = (max(1, round(base_size[0] * scale)), max(1, round(base_size[1] * scale)))
    return pygame.transform.smoothscale(surface, size)


def padlock(colour, scale=1.0):
    """Return a closed padlock icon in the given colour (drawn on locked gates)."""
    cache_key = ("padlock", colour, scale)
    if cache_key not in _cache:
        k = DETAIL
        surface = pygame.Surface((PADLOCK_SIZE[0] * k, PADLOCK_SIZE[1] * k), pygame.SRCALPHA)
        metal = (214, 218, 230)

        # Shackle: a half circle on two legs.
        pygame.draw.arc(surface, OUTLINE, (5 * k, 5 * k, 18 * k, 18 * k), 0, 3.1416, 6 * k)
        pygame.draw.arc(surface, metal, (6 * k, 6 * k, 16 * k, 16 * k), 0, 3.1416, 4 * k)
        pygame.draw.rect(surface, metal, (6 * k, 14 * k, 4 * k, 7 * k))
        pygame.draw.rect(surface, metal, (18 * k, 14 * k, 4 * k, 7 * k))

        # Body with a highlight and a keyhole.
        body = pygame.Rect(2 * k, 19 * k, 24 * k, 19 * k)
        pygame.draw.rect(surface, colour, body, border_radius=5 * k)
        pygame.draw.rect(surface, _shade(colour, 1.3), (5 * k, 21 * k, 18 * k, 4 * k), border_radius=2 * k)
        pygame.draw.rect(surface, OUTLINE, body, 2 * k, border_radius=5 * k)
        pygame.draw.circle(surface, KEYHOLE, (14 * k, 28 * k), 3 * k)
        pygame.draw.rect(surface, KEYHOLE, (13 * k, 28 * k, 3 * k, 6 * k))
        _cache[cache_key] = _finish(surface, PADLOCK_SIZE, scale)
    return _cache[cache_key]


def key(colour, scale=1.0):
    """Return a key icon in the given colour: a ring, a shaft and two teeth."""
    cache_key = ("key", colour, scale)
    if cache_key not in _cache:
        k = DETAIL
        surface = pygame.Surface((KEY_SIZE[0] * k, KEY_SIZE[1] * k), pygame.SRCALPHA)
        dark = _shade(colour, 0.55)

        # Shaft and teeth first, so the ring sits on top of the shaft's end.
        pygame.draw.rect(surface, dark, (16 * k, 8 * k, 28 * k, 8 * k), border_radius=2 * k)
        pygame.draw.rect(surface, colour, (17 * k, 9 * k, 26 * k, 6 * k), border_radius=2 * k)
        pygame.draw.rect(surface, dark, (32 * k, 14 * k, 5 * k, 8 * k))
        pygame.draw.rect(surface, colour, (33 * k, 14 * k, 3 * k, 7 * k))
        pygame.draw.rect(surface, dark, (39 * k, 14 * k, 5 * k, 6 * k))
        pygame.draw.rect(surface, colour, (40 * k, 14 * k, 3 * k, 5 * k))
        pygame.draw.rect(surface, _shade(colour, 1.4), (19 * k, 10 * k, 21 * k, k))

        # Ring with a see-through hole.
        pygame.draw.circle(surface, dark, (11 * k, 12 * k), 11 * k)
        pygame.draw.circle(surface, colour, (11 * k, 12 * k), 9 * k)
        pygame.draw.circle(surface, _shade(colour, 1.35), (8 * k, 9 * k), 3 * k)
        pygame.draw.circle(surface, dark, (11 * k, 12 * k), 4 * k)
        pygame.draw.circle(surface, (0, 0, 0, 0), (11 * k, 12 * k), 3 * k)
        _cache[cache_key] = _finish(surface, KEY_SIZE, scale)
    return _cache[cache_key]
