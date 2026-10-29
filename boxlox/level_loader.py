"""Read level text files from disk and turn them into Board objects.

A level file looks like this:

    name: First Lock
    start: 1 1
    grid:
     ........
     ..S..b..
     .o...b..
     ....K..#G
    links:
    lock 3 1 red
    key 5 3 red
    gate 8 3 red
    switch 2 2 bridge 6 1 6 2

Coordinates are "x y" with (0, 0) at the top-left of the grid. For a lying
lock ("=" or "H") the coordinate is its left or top cell.
"""

import os

from boxlox import board as b

COLOURS = ("red", "blue", "green", "yellow", "purple")


class LevelError(Exception):
    """Raised when a level file is missing or malformed."""

    def __init__(self, path, line_number, message):
        where = f"{path}, line {line_number}" if line_number else path
        super().__init__(f"{where}: {message}")


def load_all_levels(folder):
    """Load every .txt file in the folder, in filename order."""
    if not os.path.isdir(folder):
        raise LevelError(folder, None, "levels folder not found")
    names = sorted(name for name in os.listdir(folder) if name.endswith(".txt"))
    if not names:
        raise LevelError(folder, None, "no .txt level files found")
    return [load_level(os.path.join(folder, name)) for name in names]


def load_level(path):
    """Read one level file and return a Board."""
    try:
        with open(path, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except OSError as error:
        raise LevelError(path, None, f"could not read file ({error.strerror})")
    return _LevelParser(path, lines).parse()


class _LevelParser:
    """Parses the lines of one level file. Use load_level() rather than this."""

    def __init__(self, path, lines):
        self.path = path
        self.lines = lines
        self.name = None
        self.start = None
        self.grid = []
        self.locks = []
        self.keys = {}
        self.gates = {}
        self.switches = {}

    def error(self, line_number, message):
        """Make a LevelError pointing at this file and line."""
        return LevelError(self.path, line_number, message)

    def parse(self):
        """Read the file line by line: header, then grid, then links. Returns a Board."""
        section = "header"
        for number, line in enumerate(self.lines, start=1):
            if section == "grid":
                if line.strip() == "links:":
                    section = "links"
                else:
                    self.grid.append(line.rstrip())
            elif line.strip() == "":
                continue
            elif section == "header":
                if line.strip() == "grid:":
                    section = "grid"
                else:
                    self.parse_header(number, line)
            else:
                self.parse_link(number, line)

        # Blank lines at the end of the grid are just spacing, not rows.
        while self.grid and self.grid[-1] == "":
            self.grid.pop()

        self.check_complete()
        return b.Board(self.name, self.grid, self.start, self.locks,
                       self.keys, self.gates, self.switches)

    # ----- header -----

    def parse_header(self, number, line):
        """Read a 'name:', 'start:' or 'grid:' line."""
        if ":" not in line:
            raise self.error(number, f"expected 'name:', 'start:' or 'grid:', got {line.strip()!r}")
        field, value = (part.strip() for part in line.split(":", 1))
        if field == "name":
            self.name = value
        elif field == "start":
            self.start = self.read_coords(number, value.split(), 2)[0]
        else:
            raise self.error(number, f"unknown field {field!r}")

    # ----- links -----

    def parse_link(self, number, line):
        """Read one link line (lock, key, gate or switch) and send it to its parser."""
        words = line.split()
        kind = words[0]
        if kind == "lock":
            self.parse_lock(number, words)
        elif kind == "key":
            self.parse_key(number, words)
        elif kind == "gate":
            self.parse_gate(number, words)
        elif kind == "switch":
            self.parse_switch(number, words)
        else:
            raise self.error(number, f"unknown link {kind!r} (use lock, key, gate or switch)")

    def parse_lock(self, number, words):
        """Read 'lock X Y COLOUR' and check the cells match the lock's symbol."""
        (x, y), = self.read_coords(number, words[1:3], 2)
        colour = self.read_colour(number, words, 3)
        symbol = self.tile(x, y)
        if symbol not in b.LOCK_SYMBOLS:
            raise self.error(number, f"no lock tile at {x} {y}")
        if any(lock.colour == colour for lock in self.locks):
            raise self.error(number, f"there is already a {colour} lock")
        lock = b.Lock(colour, b.LOCK_SYMBOLS[symbol], x, y)
        # A lying lock needs its second cell marked with the same symbol.
        if any(self.tile(cx, cy) != symbol for cx, cy in lock.cells):
            raise self.error(number, f"lock at {x} {y} needs both of its cells marked {symbol!r}")
        self.locks.append(lock)

    def parse_key(self, number, words):
        """Read 'key X Y COLOUR' and check there is a key tile there."""
        (x, y), = self.read_coords(number, words[1:3], 2)
        colour = self.read_colour(number, words, 3)
        if self.tile(x, y) != b.KEY:
            raise self.error(number, f"no key tile 'K' at {x} {y}")
        if colour in self.keys:
            raise self.error(number, f"there is already a {colour} key")
        self.keys[colour] = b.Key(colour, x, y)

    def parse_gate(self, number, words):
        """Read 'gate X Y COLOUR' and check there is a gate tile there."""
        (x, y), = self.read_coords(number, words[1:3], 2)
        colour = self.read_colour(number, words, 3)
        if self.tile(x, y) != b.GATE:
            raise self.error(number, f"no gate tile '#' at {x} {y}")
        self.gates.setdefault(colour, []).append((x, y))

    def parse_switch(self, number, words):
        """Read 'switch X Y bridge X1 Y1 ...' and check the switch and bridge cells."""
        if len(words) < 6 or words[3] != "bridge":
            raise self.error(number, "expected 'switch X Y bridge X1 Y1 [X2 Y2 ...]'")
        (x, y), = self.read_coords(number, words[1:3], 2)
        symbol = self.tile(x, y)
        if symbol not in b.SWITCH_SYMBOLS:
            raise self.error(number, f"no switch tile ('o' or 'X') at {x} {y}")
        bridge_cells = self.read_coords(number, words[4:], None)
        for bx, by in bridge_cells:
            if self.tile(bx, by) not in b.BRIDGE_SYMBOLS:
                raise self.error(number, f"no bridge tile ('b' or 'B') at {bx} {by}")
        self.switches[(x, y)] = b.Switch(x, y, symbol == b.HEAVY_SWITCH, bridge_cells)

    # ----- helpers -----

    def tile(self, x, y):
        """The grid symbol at (x, y), or empty space if it is outside the grid."""
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]):
            return self.grid[y][x]
        return b.VOID

    def read_coords(self, number, words, count):
        """Turn ["1", "2", "3", "4"] into [(1, 2), (3, 4)].

        count is how many numbers are expected, or None for any even number.
        """
        if (count is not None and len(words) != count) or len(words) % 2 or not words:
            raise self.error(number, f"expected x y coordinates, got {' '.join(words)!r}")
        try:
            numbers = [int(word) for word in words]
        except ValueError:
            raise self.error(number, f"coordinates must be whole numbers, got {' '.join(words)!r}")
        return list(zip(numbers[0::2], numbers[1::2]))

    def read_colour(self, number, words, index):
        """Read the colour word at words[index] and check it is a known colour."""
        if len(words) != index + 1:
            raise self.error(number, f"expected '{words[0]} X Y COLOUR'")
        colour = words[index].lower()
        if colour not in COLOURS:
            raise self.error(number, f"unknown colour {colour!r} (use {', '.join(COLOURS)})")
        return colour

    def check_complete(self):
        """Check the level as a whole once every line has been read."""
        if self.name is None:
            raise self.error(None, "missing 'name:' line")
        if self.start is None:
            raise self.error(None, "missing 'start:' line")
        if not self.grid:
            raise self.error(None, "missing or empty 'grid:' section")
        if not any(b.GOAL in row for row in self.grid):
            raise self.error(None, "the grid has no goal 'G'")
        has_spin = any(b.SPIN in row for row in self.grid)
        if any(b.GOAL_ALT in row for row in self.grid) and not has_spin:
            raise self.error(None, "a second goal 'g' needs a spin tile '@' to open it")

        sx, sy = self.start
        if self.tile(sx, sy) in (b.VOID, b.FRAGILE, b.GATE, b.BRIDGE_OFF):
            raise self.error(None, f"the block can't start standing at {sx} {sy}")

        # Every special tile in the grid must be linked to something.
        lock_cells = {cell for lock in self.locks for cell in lock.cells}
        key_cells = {key.cell for key in self.keys.values()}
        gate_cells = {cell for cells in self.gates.values() for cell in cells}
        for y, row in enumerate(self.grid):
            for x, symbol in enumerate(row):
                if symbol in b.LOCK_SYMBOLS and (x, y) not in lock_cells:
                    raise self.error(None, f"lock tile at {x} {y} has no 'lock' line")
                if symbol == b.KEY and (x, y) not in key_cells:
                    raise self.error(None, f"key tile at {x} {y} has no 'key' line")
                if symbol == b.GATE and (x, y) not in gate_cells:
                    raise self.error(None, f"gate tile at {x} {y} has no 'gate' line")
                if symbol in b.SWITCH_SYMBOLS and (x, y) not in self.switches:
                    raise self.error(None, f"switch at {x} {y} has no 'switch' line")

        # Each colour needs its lock and key together, and gates need a key.
        lock_colours = {lock.colour for lock in self.locks}
        for colour in lock_colours ^ set(self.keys):
            raise self.error(None, f"the {colour} lock and key must both exist")
        for colour in self.gates:
            if colour not in self.keys:
                raise self.error(None, f"the {colour} gates have no {colour} key to open them")
