"""The moving scene behind the title screen.

Two layers:
- a game-themed background: stars, plus little islands of game tiles and
  faint keys and padlocks drifting slowly upwards at different depths;
- a small demo strip of floating tiles where the block plays by itself:
  it drops in, rolls up to a gap, stops and peeks over the edge, a bridge
  rises, and it rolls across and sinks into the goal. Then it loops.
"""

import math
import random

import pygame
from pygame import gfxdraw

from boxlox import icons
from boxlox.block import Block, RIGHT
from boxlox.board import Board
from boxlox.renderer import (Renderer, X_AXIS, Y_AXIS, UNIT, TILE_DEPTH, COLOURS,
                             FLOOR_COLOUR, FRAGILE_COLOUR, SPIN_COLOUR, BRIDGE_COLOUR, shade)

DEMO_GRID = [
    "......b...",
    "......b..G",
    "......b...",
]
DEMO_START = (0, 1)
BRIDGE_CELLS = [(6, 0), (6, 1), (6, 2)]
DEMO_CENTRE_Y = 306   # where the strip sits on a 960x640 screen (just under the logo)
DEMO_ZOOM = 0.87      # the strip is drawn a little smaller than a real level, so the logo leads

# Background depth layers, far to near: (size, how many, brightness, colour strength, opacity).
# Far things are small, dark, greyish and faint; near things are bigger, brighter and kept
# to the sides, so they frame the middle instead of cluttering it.
LAYERS = (
    (0.38, 7, 0.50, 0.30, 110),
    (0.58, 5, 0.72, 0.60, 160),
    (0.82, 4, 1.00, 1.00, 225),
)

ROLL_TIME = 0.32      # a little slower than in the game, so it reads as calm

# The demo's script: (action, seconds). Three rolls bring it to the edge of
# the gap; it peeks, the bridge rises, and three more rolls reach the goal.
SCRIPT = (
    ("drop", 0.55), ("wait", 0.3),
    ("roll", ROLL_TIME), ("wait", 0.12), ("roll", ROLL_TIME), ("wait", 0.12), ("roll", ROLL_TIME),
    ("wait", 0.45), ("peek", 0.7), ("wait", 0.25), ("bridge", 0.45), ("wait", 0.35),
    ("roll", ROLL_TIME), ("wait", 0.12), ("roll", ROLL_TIME), ("wait", 0.12), ("roll", ROLL_TIME),
    ("sink", 0.7), ("wait", 0.7),
)


def faded(colour, brightness, strength):
    """Make a colour look further away: greyer (strength < 1) and darker (brightness < 1)."""
    grey = 0.3 * colour[0] + 0.59 * colour[1] + 0.11 * colour[2]
    return tuple(max(0, min(255, int((grey + (c - grey) * strength) * brightness))) for c in colour)


def darkened(sprite, brightness):
    """Return a copy of an icon with every colour multiplied by brightness."""
    sprite = sprite.copy()
    level = int(255 * brightness)
    sprite.fill((level, level, level, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return sprite


def island_sprite(cells, colour, scale):
    """Draw a little floating group of tiles onto its own see-through surface."""
    ax = (X_AXIS[0] * scale, X_AXIS[1] * scale)
    ay = (Y_AXIS[0] * scale, Y_AXIS[1] * scale)
    unit = UNIT * scale

    def project(x, y, z):
        return (x * ax[0] + y * ay[0], x * ax[1] + y * ay[1] - z * unit)

    corners = [project(x + dx, y + dy, z) for x, y in cells
               for dx in (0, 1) for dy in (0, 1) for z in (0, -TILE_DEPTH)]
    left = min(p[0] for p in corners) - 2
    top = min(p[1] for p in corners) - 2
    width = int(max(p[0] for p in corners) - left) + 4
    height = int(max(p[1] for p in corners) - top) + 4
    surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def poly(fill, points):
        points = [(round(px - left), round(py - top)) for px, py in points]
        gfxdraw.filled_polygon(surface, points, fill)
        gfxdraw.aapolygon(surface, points, shade(fill, 0.6))

    d = -TILE_DEPTH
    for x, y in sorted(cells, key=lambda c: c[1] + 0.35 * c[0]):
        poly(shade(colour, 0.72), [project(x, y + 1, d), project(x + 1, y + 1, d),
                                   project(x + 1, y + 1, 0), project(x, y + 1, 0)])
        poly(shade(colour, 0.5), [project(x + 1, y, d), project(x + 1, y + 1, d),
                                  project(x + 1, y + 1, 0), project(x + 1, y, 0)])
        poly(colour, [project(x, y, 0), project(x + 1, y, 0), project(x + 1, y + 1, 0), project(x, y + 1, 0)])
    return surface


class Drifter:
    """One background decoration slowly floating upwards (a tile island, key or padlock)."""

    def __init__(self, sprite, x, y, speed, alpha, spin=0.0):
        self.sprite = sprite
        self.x = x
        self.y = y
        self.speed = speed
        self.alpha = alpha
        self.spin = spin
        self.phase = random.uniform(0, math.tau)


class TitleScene:
    """Draws and animates everything behind the title screen's logo and buttons."""

    def __init__(self, screen):
        self.screen = screen
        self.renderer = Renderer(screen)
        self.s = self.renderer.s
        self.board = Board("title", list(DEMO_GRID), DEMO_START, [], {}, {}, {})
        self.renderer.set_zoom(DEMO_ZOOM)
        self.renderer.centre_on(self.board)
        # Move the strip so its middle sits at DEMO_CENTRE_Y.
        _, middle_y = self.renderer.project(self.renderer.pivot[0], self.renderer.pivot[1], 0)
        self.renderer.origin_y += DEMO_CENTRE_Y * self.s - middle_y
        self.drifters = self._make_drifters()
        self.time = 0.0
        self.restart_loop()

    # ----- background -----

    def _make_drifters(self):
        """Spread decorations evenly across three depth layers (not randomly scattered)."""
        width, height = self.screen.get_size()
        shapes = [[(0, 0)], [(0, 0), (1, 0)], [(0, 0), (0, 1)], [(0, 0), (1, 0), (1, 1)],
                  [(0, 0), (1, 0), (0, 1), (1, 1)], [(0, 0), (1, 0), (2, 0)]]
        tile_colours = [FLOOR_COLOUR, FLOOR_COLOUR, FRAGILE_COLOUR, SPIN_COLOUR, BRIDGE_COLOUR]
        key_colours = list(COLOURS.values())
        drifters = []
        for layer, (size, count, brightness, strength, alpha) in enumerate(LAYERS):
            near = layer == len(LAYERS) - 1
            for i in range(count):
                # Even slots across the screen with a little jitter. The nearest
                # layer sits only in the side margins, framing the logo and strip.
                if near:
                    side = i % 2
                    x = width * (random.uniform(0.04, 0.17) if side == 0 else random.uniform(0.83, 0.96))
                else:
                    x = width * (i + random.uniform(0.25, 0.75)) / count
                y = height * (i + random.uniform(0.2, 0.8)) / count + layer * height / 7
                scale = size * self.s
                if i % 3 == 2:   # every third decoration is a key or padlock
                    colour = faded(key_colours[(i + layer) % len(key_colours)], 1.0, strength)
                    icon = icons.key(colour, scale * 1.2) if (i + layer) % 2 else icons.padlock(colour, scale * 1.2)
                    sprite, spin = darkened(icon, brightness), random.uniform(-25, 25)
                else:
                    colour = faded(tile_colours[(i * 2 + layer) % len(tile_colours)], brightness, strength)
                    sprite, spin = island_sprite(shapes[(i + layer * 2) % len(shapes)], colour, scale), 0.0
                drifters.append(Drifter(sprite, x, y, (6 + 26 * size) * self.s, alpha, spin))
        return drifters   # already far-to-near, so nearer ones are drawn on top

    def draw_background(self, time):
        """Draw the sky and the decorations drifting slowly upwards."""
        self.renderer.draw_background(time)
        width, height = self.screen.get_size()
        for d in self.drifters:
            # Drift upwards, wrapping round from the top back to the bottom, with a gentle sway.
            span = height + d.sprite.get_height() * 2
            y = (d.y - time * d.speed) % span - d.sprite.get_height()
            x = d.x + 12 * self.s * math.sin(time * 0.5 + d.phase)
            sprite = d.sprite
            if d.spin:
                sprite = pygame.transform.rotozoom(sprite, math.sin(time * 0.4 + d.phase) * d.spin, 1)
            sprite = sprite.copy()
            sprite.set_alpha(d.alpha)
            self.screen.blit(sprite, sprite.get_rect(center=(x, y)))

    # ----- demo loop -----

    def restart_loop(self):
        """Put the demo block back at the start with the bridge down."""
        self.step = 0
        self.step_time = 0.0
        self.block = Block(DEMO_START[0], DEMO_START[1])
        self.board.bridges_on = frozenset()

    def update(self, dt):
        """Advance the demo script by dt seconds."""
        self.time += dt
        self.step_time += dt
        action, length = SCRIPT[self.step]
        if self.step_time < length:
            return
        # The step has finished: apply its result, then start the next one.
        self.step_time -= length
        if action == "roll":
            self.block = self.block.roll(RIGHT)
        elif action == "bridge":
            self.board.bridges_on = frozenset(BRIDGE_CELLS)
        self.step += 1
        if self.step == len(SCRIPT):
            self.restart_loop()

    def draw(self):
        """Draw the background and the demo strip with the block where the script says."""
        self.draw_background(self.time)
        action, length = SCRIPT[self.step]
        progress = min(self.step_time / length, 1.0)
        eased = progress * progress * (3 - 2 * progress)

        block, roll, z, clip, show = self.block, None, 0.0, False, True
        tile_rise = {}
        if action == "drop":
            z = 5.0 * (1 - progress * progress)            # falls in from above, speeding up
        elif action == "roll":
            roll = (self.block.roll(RIGHT), RIGHT, eased)
        elif action == "peek":
            # Lean over the edge and back, as if looking at the gap.
            roll = (self.block.roll(RIGHT), RIGHT, 0.16 * math.sin(math.pi * progress))
        elif action == "bridge":
            self.board.bridges_on = frozenset(BRIDGE_CELLS)
            tile_rise = {cell: -1.4 * (1 - eased) ** 2 for cell in BRIDGE_CELLS}
        elif action == "sink":
            z, clip = -2.0 * progress * progress, True
        elif action == "wait" and self.step == len(SCRIPT) - 1:
            show = False                                    # gone down the hole

        self.renderer.draw(self.board, block, self.time, block_z=z, clip_floor=clip, show_block=show,
                           roll=roll, tile_rise=tile_rise, background=False)
