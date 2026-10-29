"""3D-looking drawing of the board and block.

Everything is drawn as boxes in a 3D "world" where x and y are grid cells
and z is height (the floor top is z = 0). project() turns a world point into
a screen pixel, so the game logic never has to know about pixels.

The camera looks at the board from in front and a little to the right, like
Bloxorz: grid x runs almost left-to-right on screen and grid y runs from the
back of the board towards the player. That way the arrow keys match what
the player sees.

A spin tile turns the whole view about the middle of the board. project()
rotates every world point by the view angle first, so everything else
(tiles, block, keys, shadows) turns with it automatically.
"""

import math
import random

import pygame
from pygame import gfxdraw

from boxlox import board as b
from boxlox import icons
from boxlox.display import scale_of
from boxlox.block import UP, DOWN, LEFT, RIGHT

# Sizes are for the 960x640 design size; the Renderer multiplies them by the
# window's scale so the game is drawn sharp on high-resolution screens.
X_AXIS = (46, 9)    # screen pixels moved by one cell in +x (right, slightly down)
Y_AXIS = (-16, 27)  # screen pixels moved by one cell in +y (towards the player)
UNIT = 34           # screen pixels per unit of height
TILE_DEPTH = 0.35   # thickness of a floor tile, in height units

# The direction from the board towards the camera. A box face is only
# visible if it points this way. (Worked out from the two axes above.)
VIEW = (-Y_AXIS[0] * UNIT, X_AXIS[0] * UNIT, X_AXIS[0] * Y_AXIS[1] - Y_AXIS[0] * X_AXIS[1])

# The direction light comes from: above, slightly behind and to the left.
_light_length = math.sqrt(0.3 ** 2 + 0.5 ** 2 + 1.0)
LIGHT = (-0.3 / _light_length, 0.5 / _light_length, 1.0 / _light_length)

BACKGROUND_TOP = (10, 12, 30)
BACKGROUND_BOTTOM = (52, 28, 76)
FLOOR_COLOUR = (196, 204, 224)
BRIDGE_COLOUR = (150, 176, 214)
FRAGILE_COLOUR = (240, 146, 56)
HOLE_COLOUR = (8, 8, 16)
GOAL_GLOW = (255, 214, 110)
SWITCH_COLOUR = (88, 96, 118)
SPIN_COLOUR = (150, 118, 220)
DEPTH_SLOPE = 0.35  # how much further away a cell is per step in view x, vs. view y
BLOCK_COLOUR = (236, 180, 86)
TEXT_COLOUR = (238, 238, 248)

COLOURS = {
    "red": (232, 70, 70),
    "blue": (70, 132, 240),
    "green": (66, 192, 102),
    "yellow": (244, 210, 60),
    "purple": (172, 98, 224),
}

# The 6 faces of a box, as indexes into its 8 corners, with their outward normals.
# Corner i is at (x1 if i & 1 else x0, y1 if i & 2 else y0, z1 if i & 4 else z0).
FACES = (
    ((0, 2, 6, 4), (-1, 0, 0)),
    ((1, 3, 7, 5), (1, 0, 0)),
    ((0, 1, 5, 4), (0, -1, 0)),
    ((2, 3, 7, 6), (0, 1, 0)),
    ((0, 1, 3, 2), (0, 0, -1)),
    ((4, 5, 7, 6), (0, 0, 1)),
)


def shade(colour, factor):
    """Return the colour made darker (factor < 1) or lighter (factor > 1)."""
    return tuple(max(0, min(255, int(channel * factor))) for channel in colour)


def blend(colour_a, colour_b, amount):
    """Mix two colours. amount = 0 gives colour_a, 1 gives colour_b."""
    return tuple(int(a + (c - a) * amount) for a, c in zip(colour_a, colour_b))


def dot(a, c):
    return a[0] * c[0] + a[1] * c[1] + a[2] * c[2]


def box_corners(x0, y0, z0, x1, y1, z1):
    """Return the 8 corners of an upright box, in the order FACES expects."""
    return [
        (x1 if i & 1 else x0, y1 if i & 2 else y0, z1 if i & 4 else z0)
        for i in range(8)
    ]


def rotate(point, direction, pivot, angle):
    """Rotate a point about a floor edge, the way the block tips when rolling.

    The edge runs along y (for LEFT/RIGHT) or x (for UP/DOWN) at height 0,
    positioned at `pivot`. The top of the block swings towards `direction`.
    """
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    if direction == RIGHT:
        d = x - pivot
        return (pivot + d * c + z * s, y, -d * s + z * c)
    if direction == LEFT:
        d = x - pivot
        return (pivot + d * c - z * s, y, d * s + z * c)
    if direction == DOWN:
        d = y - pivot
        return (x, pivot + d * c + z * s, -d * s + z * c)
    d = y - pivot
    return (x, pivot + d * c - z * s, d * s + z * c)


def block_bounds(block):
    """Return (x0, y0, x1, y1, height) of the box a block takes up."""
    cells = block.cells()
    x0 = min(x for x, _ in cells)
    y0 = min(y for _, y in cells)
    x1 = max(x for x, _ in cells) + 1
    y1 = max(y for _, y in cells) + 1
    height = 2 if len(cells) == 1 else 1
    return x0, y0, x1, y1, height


class Renderer:
    """Draws a Board and Block onto a Pygame surface."""

    def __init__(self, screen):
        self.screen = screen
        self.origin_x = 0
        self.origin_y = 0
        self.offset = (0, 0)  # screen shake, set by the game each frame
        self.pivot = (0.0, 0.0)  # the board's middle, which the view spins around
        self.set_view_angle(0.0)
        self.s = s = scale_of(screen.get_size())
        self.x_axis = (X_AXIS[0] * s, X_AXIS[1] * s)
        self.y_axis = (Y_AXIS[0] * s, Y_AXIS[1] * s)
        self.unit = UNIT * s
        self.font = pygame.font.Font(None, round(30 * s))
        self.small_font = pygame.font.Font(None, round(24 * s))
        self.card_font = pygame.font.Font(None, round(72 * s))
        self.card_small_font = pygame.font.Font(None, round(40 * s))
        self.background = self._make_background()
        width, height = screen.get_size()
        self.stars = [
            (random.uniform(0, width), random.uniform(0, height),
             random.uniform(0, math.tau), random.uniform(0.6, 2.2), max(1, round(random.choice((1, 1, 1, 2)) * s)))
            for _ in range(130)
        ]

    def _make_background(self):
        """Pre-draw a vertical gradient so it doesn't need redrawing each frame."""
        width, height = self.screen.get_size()
        surface = pygame.Surface((width, height))
        for y in range(height):
            colour = blend(BACKGROUND_TOP, BACKGROUND_BOTTOM, y / height)
            pygame.draw.line(surface, colour, (0, y), (width, y))
        return surface

    def draw_background(self, time):
        """Draw the gradient sky with gently twinkling stars."""
        self.screen.blit(self.background, (0, 0))
        for x, y, phase, speed, radius in self.stars:
            brightness = 0.5 + 0.5 * math.sin(time * speed + phase)
            colour = blend((70, 70, 110), (240, 240, 255), brightness)
            gfxdraw.filled_circle(self.screen, int(x), int(y), radius, colour)
            gfxdraw.aacircle(self.screen, int(x), int(y), radius, colour)

    # ----- coordinates -----

    def set_zoom(self, factor):
        """Draw boards smaller (< 1) or bigger (> 1) than normal. Call before centre_on()."""
        s = self.s * factor
        self.x_axis = (X_AXIS[0] * s, X_AXIS[1] * s)
        self.y_axis = (Y_AXIS[0] * s, Y_AXIS[1] * s)
        self.unit = UNIT * s

    def set_view_angle(self, angle):
        """Turn the view by angle radians about the board's middle (0 = normal)."""
        self.view_cos = math.cos(angle)
        self.view_sin = math.sin(angle)

    def view_xy(self, wx, wy):
        """Rotate a floor position by the current view angle about the pivot."""
        dx, dy = wx - self.pivot[0], wy - self.pivot[1]
        return (self.pivot[0] + dx * self.view_cos - dy * self.view_sin,
                self.pivot[1] + dx * self.view_sin + dy * self.view_cos)

    def project(self, wx, wy, wz):
        """Turn a world point (cells, cells, height units) into a screen point."""
        wx, wy = self.view_xy(wx, wy)
        sx = self.origin_x + self.offset[0] + wx * self.x_axis[0] + wy * self.y_axis[0]
        sy = self.origin_y + self.offset[1] + wx * self.x_axis[1] + wy * self.y_axis[1] - wz * self.unit
        return (sx, sy)

    def depth(self, x, y):
        """How far forward a floor position is in the current view (bigger = nearer)."""
        vx, vy = self.view_xy(x, y)
        return vy + DEPTH_SLOPE * vx

    def centre_on(self, board):
        """Spin around the board's middle, and put that middle in the middle of the screen."""
        cells = [(x, y) for y, row in enumerate(board.grid) for x, symbol in enumerate(row) if symbol != b.VOID]
        xs = [x for x, _ in cells]
        ys = [y for _, y in cells]
        self.pivot = ((min(xs) + max(xs) + 1) / 2, (min(ys) + max(ys) + 1) / 2)
        self.origin_x = self.origin_y = 0
        saved_offset, self.offset = self.offset, (0, 0)
        middle_x, middle_y = self.project(self.pivot[0], self.pivot[1], 0)
        self.offset = saved_offset
        width, height = self.screen.get_size()
        self.origin_x = width / 2 - middle_x
        # Nudge down a little so a standing block at the back stays on screen.
        self.origin_y = height / 2 - middle_y + self.unit * 0.9

    # ----- shapes -----

    def _fill(self, colour, points, surface=None):
        """Draw a filled polygon with smooth (anti-aliased) edges."""
        points = [(round(x), round(y)) for x, y in points]
        target = surface or self.screen
        gfxdraw.filled_polygon(target, points, colour)
        gfxdraw.aapolygon(target, points, colour)

    def _outline(self, colour, points, width=1):
        """Draw a polygon outline with smooth edges. Wider outlines get a smooth outer edge."""
        points = [(round(x), round(y)) for x, y in points]
        width = round(width * self.s)
        if width > 1:
            pygame.draw.lines(self.screen, colour, True, points, width)
        gfxdraw.aapolygon(self.screen, points, colour)

    def _line(self, colour, start, end, width=1):
        """Draw a line with smooth edges."""
        width = round(width * self.s)
        if width > 1:
            pygame.draw.line(self.screen, colour, start, end, width)
        pygame.draw.aaline(self.screen, colour, start, end)

    def _solid(self, corners, normals, colour):
        """Draw a box from its 8 corners, lit by LIGHT. Hidden faces are skipped."""
        edge = shade(colour, 0.42)
        c, s = self.view_cos, self.view_sin
        for (indexes, _), (nx, ny, nz) in zip(FACES, normals):
            # Turn the normal with the view so lighting and hidden faces stay right.
            normal = (nx * c - ny * s, nx * s + ny * c, nz)
            if dot(normal, VIEW) <= 1e-6:
                continue
            brightness = 0.45 + 0.6 * max(0.0, dot(normal, LIGHT))
            points = [self.project(*corners[i]) for i in indexes]
            self._fill(shade(colour, brightness), points)
            self._outline(edge, points)

    def _flat_box(self, x0, y0, x1, y1, z0, z1, colour):
        """Draw an upright box with a soft highlight along its top back edges."""
        self._solid(box_corners(x0, y0, z0, x1, y1, z1), [n for _, n in FACES], colour)
        p = self.project
        light = shade(colour, 1.18)
        # Set just inside the edge so it doesn't fight with the dark outline.
        inset = 0.04
        self._line(light, p(x0 + inset, y0 + inset, z1), p(x1 - inset, y0 + inset, z1))
        self._line(light, p(x0 + inset, y0 + inset, z1), p(x0 + inset, y1 - inset, z1))

    def _alpha_polygon(self, colour, alpha, points):
        """Draw a see-through polygon (Pygame can't do this directly on the screen)."""
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        left, top = int(min(xs)), int(min(ys))
        size = (int(max(xs)) - left + 2, int(max(ys)) - top + 2)
        surface = pygame.Surface(size, pygame.SRCALPHA)
        self._fill((*colour, alpha), [(x - left, y - top) for x, y in points], surface)
        self.screen.blit(surface, (left, top))

    def _area(self, x0, y0, x1, y1, z=0.0):
        """Return the 4 screen corners of a flat rectangle on the floor."""
        p = self.project
        return [p(x0, y0, z), p(x1, y0, z), p(x1, y1, z), p(x0, y1, z)]

    def _blit_centred(self, surface, position):
        """Blit a surface with its centre at position."""
        self.screen.blit(surface, surface.get_rect(center=(round(position[0]), round(position[1]))))

    # ----- tiles -----

    def _draw_tile(self, board, x, y, time, rise, revealed):
        """Draw one tile at (x, y), including any icon on top (lock, key, switch, ...)."""
        symbol = board.tile(x, y)
        cell = (x, y)

        if symbol in b.BRIDGE_SYMBOLS and cell not in board.bridges_on:
            # An off bridge is just a faint outline showing where it will appear.
            self._outline(shade(BRIDGE_COLOUR, 0.55), self._area(x + 0.05, y + 0.05, x + 0.95, y + 0.95))
            return

        if symbol == b.GATE:
            colour = COLOURS[board.gate_colour(cell)]
            if board.is_solid(x, y):
                self._flat_box(x, y, x + 1, y + 1, -TILE_DEPTH + rise, rise, blend(FLOOR_COLOUR, colour, 0.45))
            else:
                # A closed gate is a see-through coloured panel with a padlock on it.
                pulse = 0.5 + 0.5 * math.sin(time * 3 + x + y)
                area = self._area(x + 0.04, y + 0.04, x + 0.96, y + 0.96)
                self._alpha_polygon(colour, int(40 + 30 * pulse), area)
                self._outline(colour, area, 2)
                self._blit_centred(icons.padlock(colour, self.s), self.project(x + 0.5, y + 0.5, 0.35))
            return

        colours = {b.FRAGILE: FRAGILE_COLOUR, b.BRIDGE_ON: BRIDGE_COLOUR, b.BRIDGE_OFF: BRIDGE_COLOUR}
        colour = colours.get(symbol, FLOOR_COLOUR)
        # An undiscovered spin tile is drawn as plain floor: it's a mystery.
        spin_shown = symbol == b.SPIN and cell in revealed
        if spin_shown:
            colour = blend(FLOOR_COLOUR, SPIN_COLOUR, 0.25 if board.goals_swapped else 0.55)
        if (x + y) % 2:
            colour = shade(colour, 0.95)  # a faint checkerboard makes cells easier to count
        self._flat_box(x, y, x + 1, y + 1, -TILE_DEPTH + rise, rise, colour)

        if symbol == b.GOAL_ALT and symbol != board.open_goal():
            pass  # the second goal is a secret: plain floor until the spin tile opens it
        elif symbol == b.GOAL and symbol != board.open_goal():
            # The first goal after a spin: a closed hatch set into the tile.
            self._fill(shade(colour, 0.78), self._area(x + 0.14, y + 0.14, x + 0.86, y + 0.86))
            self._outline(shade(colour, 0.5), self._area(x + 0.14, y + 0.14, x + 0.86, y + 0.86), 2)
            self._line(shade(colour, 0.6), self.project(x + 0.14, y + 0.5, 0), self.project(x + 0.86, y + 0.5, 0), 2)
        elif symbol in (b.GOAL, b.GOAL_ALT):
            pulse = 0.5 + 0.5 * math.sin(time * 3)
            self._alpha_polygon(GOAL_GLOW, int(70 + 90 * pulse), self._area(x + 0.03, y + 0.03, x + 0.97, y + 0.97))
            self._fill(shade(HOLE_COLOUR, 3), self._area(x + 0.14, y + 0.14, x + 0.86, y + 0.86))
            self._fill(HOLE_COLOUR, self._area(x + 0.18, y + 0.2, x + 0.86, y + 0.86))
        elif symbol == b.SOFT_SWITCH:
            # A round button lying flat on the tile.
            for radius, colour in ((0.27, shade(SWITCH_COLOUR, 0.7)), (0.21, SWITCH_COLOUR)):
                circle = [
                    self.project(x + 0.5 + radius * math.cos(a), y + 0.5 + radius * math.sin(a), 0)
                    for a in (i * math.pi / 10 for i in range(20))
                ]
                self._fill(colour, circle)
        elif spin_shown:
            # A used spin tile is spent: its arrow stops turning and fades.
            self._draw_spin_arrow(x, y, 0.0 if board.goals_swapped else time, spent=board.goals_swapped)
        elif symbol == b.HEAVY_SWITCH:
            # Joining opposite edge midpoints looks like an X on screen.
            p = self.project
            # Each bar is a thin flat rectangle so its edges can be smoothed.
            self._fill(SWITCH_COLOUR, self._area(x + 0.44, y + 0.18, x + 0.56, y + 0.82))
            self._fill(SWITCH_COLOUR, self._area(x + 0.18, y + 0.42, x + 0.82, y + 0.58))

    def _draw_spin_arrow(self, x, y, time, spent=False):
        """Draw a slowly turning circular arrow flat on a revealed spin tile."""
        colour = blend(shade(SPIN_COLOUR, 0.55), FLOOR_COLOUR, 0.55) if spent else shade(SPIN_COLOUR, 0.55)
        start = time * 1.5
        sweep = 1.6 * math.pi
        steps = 16
        points = [
            self.project(x + 0.5 + 0.26 * math.cos(start + sweep * i / steps),
                         y + 0.5 + 0.26 * math.sin(start + sweep * i / steps), 0)
            for i in range(steps + 1)
        ]
        for a, c in zip(points, points[1:]):
            self._line(colour, a, c, 3)
        # Arrowhead at the end of the arc, pointing along it.
        end = start + sweep
        tip = (0.5 + 0.26 * math.cos(end + 0.35), 0.5 + 0.26 * math.sin(end + 0.35))
        outer = (0.5 + 0.38 * math.cos(end), 0.5 + 0.38 * math.sin(end))
        inner = (0.5 + 0.14 * math.cos(end), 0.5 + 0.14 * math.sin(end))
        self._fill(colour, [self.project(x + px, y + py, 0) for px, py in (tip, outer, inner)])

    def _draw_lock(self, board, lock):
        """Draw the lock's footprint (the shape the block must fill) with a keyhole on it.

        The footprint is 1 cell for a standing lock and 2 cells for a lying
        lock, so its shape shows which pose the block needs. A solved lock
        lights up and its keyhole turns white.
        """
        colour = COLOURS[lock.colour]
        solved = lock.colour in board.solved_locks
        xs = [x for x, _ in lock.cells]
        ys = [y for _, y in lock.cells]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
        area = self._area(x0 + 0.1, y0 + 0.1, x1 - 0.1, y1 - 0.1)
        self._alpha_polygon(colour, 170 if solved else 60, area)
        self._outline(shade(colour, 0.75), area, 3)

        # A keyhole lying flat on the floor: a circle above a tapering slot.
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hole_colour = (255, 255, 255) if solved else shade(colour, 0.45)
        circle = [
            self.project(cx + 0.13 * math.cos(a), cy - 0.08 + 0.13 * math.sin(a), 0)
            for a in (i * math.pi / 8 for i in range(16))
        ]
        slot = [
            self.project(cx - 0.05, cy - 0.04, 0), self.project(cx + 0.05, cy - 0.04, 0),
            self.project(cx + 0.11, cy + 0.26, 0), self.project(cx - 0.11, cy + 0.26, 0),
        ]
        self._fill(hole_colour, circle)
        self._fill(hole_colour, slot)

    def _draw_key(self, key, time):
        """Draw a floating, slowly spinning key above its cell."""
        x, y = key.cell
        bob = 0.12 * math.sin(time * 3)
        shadow = self._area(x + 0.3, y + 0.35, x + 0.7, y + 0.65)
        self._alpha_polygon((0, 0, 0), 60, shadow)

        sprite = pygame.transform.rotozoom(icons.key(COLOURS[key.colour], self.s), 25, 1)
        spin = abs(math.cos(time * 2.2))
        width = max(2, int(sprite.get_width() * (0.25 + 0.75 * spin)))
        sprite = pygame.transform.smoothscale(sprite, (width, sprite.get_height()))
        self._blit_centred(sprite, self.project(x + 0.5, y + 0.5, 0.75 + bob))

    # ----- block -----

    def _block_shape(self, block, z, clip_floor, roll):
        """Return the block's 8 corners and 6 face normals, ready to draw.

        roll is None, or (direction, progress) while the block is tipping over.
        """
        x0, y0, x1, y1, height = block_bounds(block)
        normals = [n for _, n in FACES]
        if roll is not None:
            direction, progress = roll
            pivot = {RIGHT: x1, LEFT: x0, DOWN: y1, UP: y0}[direction]
            angle = progress * math.pi / 2
            corners = [rotate(c, direction, pivot, angle) for c in box_corners(x0, y0, 0, x1, y1, height)]
            normals = [rotate(n, direction, 0, angle) for n in normals]
            return corners, normals

        bottom, top = z, z + height
        if clip_floor:
            bottom = max(bottom, 0)  # hide the part already down the hole
            if top <= bottom:
                return None, None
        return box_corners(x0, y0, bottom, x1, y1, top), normals

    def _draw_shadow(self, board, corners, hidden):
        """Darken the floor under the block, but only on tiles that are really there."""
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        x0, y0, x1, y1 = min(xs) - 0.06, min(ys) - 0.02, max(xs) + 0.1, max(ys) + 0.08
        for cy in range(math.floor(y0), math.ceil(y1)):
            for cx in range(math.floor(x0), math.ceil(x1)):
                if (cx, cy) in hidden or not board.is_solid(cx, cy):
                    continue
                area = self._area(max(x0, cx), max(y0, cy), min(x1, cx + 1), min(y1, cy + 1))
                self._alpha_polygon((0, 0, 0), 70, area)

    def _draw_block(self, board, block, z, clip_floor, roll, hidden):
        """Draw the block with its shading, lifted by z and possibly mid-roll."""
        corners, normals = self._block_shape(block, z, clip_floor, roll)
        if corners is None:
            return
        if z == 0 and not clip_floor:
            self._draw_shadow(board, corners, hidden)
        self._solid(corners, normals, BLOCK_COLOUR)

    # ----- whole frame -----

    def draw(self, board, block, time, block_z=0.0, clip_floor=False, show_block=True,
             roll=None, hidden=(), tile_rise=None, revealed=(), background=True):
        """Draw the whole scene: background, tiles, locks, keys and block.

        roll       - None, or (new_block, direction, progress) while rolling;
                     `block` is then the block before the roll
        hidden     - cells not to draw (e.g. a fragile tile that just broke)
        tile_rise  - {cell: z offset} for tiles still rising into place
        revealed   - spin tiles the player has discovered (others look like floor)
        background - False to draw on top of whatever is already on screen
        """
        tile_rise = tile_rise or {}
        if background:
            self.draw_background(time)

        # Painter's algorithm: draw back-to-front, by how far forward each cell
        # is in the current view. The block is drawn just after the tiles at its
        # own depth, so tiles in front of it cover it when it falls below the floor.
        def cell_depth(cell):
            return self.depth(cell[0] + 0.5, cell[1] + 0.5)

        block_cells = list(block.cells())
        if roll is not None:
            block_cells += roll[0].cells()
        block_depth = max(cell_depth(cell) for cell in block_cells) + 1e-6
        cells = sorted(
            ((x, y) for y, row in enumerate(board.grid) for x, symbol in enumerate(row) if symbol != b.VOID),
            key=cell_depth,
        )
        lock_by_cell = {cell: lock for lock in board.locks for cell in lock.cells}
        key_by_cell = {key.cell: key for key in board.keys.values()}
        block_roll = None if roll is None else (roll[1], roll[2])

        block_drawn = not show_block
        for x, y in cells:
            if not block_drawn and cell_depth((x, y)) > block_depth:
                self._draw_block(board, block, block_z, clip_floor, block_roll, hidden)
                block_drawn = True
            if (x, y) in hidden:
                continue
            self._draw_tile(board, x, y, time, tile_rise.get((x, y), 0.0), revealed)
            lock = lock_by_cell.get((x, y))
            # Draw each lock once, from its last cell, so it sits on top of all its tiles.
            if lock is not None and (x, y) == lock.cells[-1]:
                self._draw_lock(board, lock)
            key = key_by_cell.get((x, y))
            if key is not None and board.key_visible(key.colour):
                self._draw_key(key, time)
        if not block_drawn:
            self._draw_block(board, block, block_z, clip_floor, block_roll, hidden)

    def _text(self, font, text, colour, position, anchor="topleft", alpha=255):
        """Draw text with a soft dark shadow underneath."""
        shadow = round(2 * self.s)
        for offset, text_colour in (((shadow, shadow), (0, 0, 0)), ((0, 0), colour)):
            surface = font.render(text, True, text_colour)
            surface.set_alpha(alpha if offset == (0, 0) else alpha // 2)
            rect = surface.get_rect(**{anchor: (position[0] + offset[0], position[1] + offset[1])})
            self.screen.blit(surface, rect)

    def draw_hud(self, level_number, level_count, board):
        """Draw the level title and collected keys in the top-left corner."""
        s = self.s
        self._text(self.font, f"Level {level_number}/{level_count}: {board.name}", TEXT_COLOUR, (20 * s, 18 * s))
        self._text(self.small_font, "Arrow keys: roll the block      Esc: pause", shade(TEXT_COLOUR, 0.7),
                   (20 * s, self.screen.get_height() - 34 * s))
        x = 20 * s
        for colour in sorted(board.collected_keys):
            self.screen.blit(icons.key(COLOURS[colour], s), (x, 50 * s))
            x += 52 * s

    def draw_pause_button(self, rect, hovered):
        """Draw the small pause button (two bars) in the top-right corner."""
        s = self.s
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (90, 98, 130, 220) if hovered else (40, 44, 62, 170), panel.get_rect(),
                         border_radius=round(8 * s))
        pygame.draw.rect(panel, (150, 160, 200, 255), panel.get_rect(), max(1, round(2 * s)), border_radius=round(8 * s))
        bar_w, bar_h = round(rect.width * 0.16), round(rect.height * 0.46)
        top = (rect.height - bar_h) // 2
        for x in (rect.width * 0.3, rect.width * 0.54):
            pygame.draw.rect(panel, TEXT_COLOUR, (round(x), top, bar_w, bar_h), border_radius=max(1, round(2 * s)))
        self.screen.blit(panel, rect)

    def draw_level_card(self, level_number, name, alpha):
        """Draw the big 'LEVEL n' title shown for a moment when a level starts."""
        width, height = self.screen.get_size()
        self._text(self.card_font, f"LEVEL {level_number}", (255, 222, 130), (width // 2, height // 4), "center", alpha)
        self._text(self.card_small_font, name, TEXT_COLOUR, (width // 2, height // 4 + 50 * self.s), "center", alpha)
