"""The board: tiles, switches, bridges, locks, keys and gates."""

from enum import Enum

from boxlox.block import Block, STANDING, LYING_X, LYING_Y

# Tile symbols used in level files
FLOOR = "."
VOID = " "
GOAL = "G"
GOAL_ALT = "g"   # second goal spot: sealed until a spin tile swaps the goals
FRAGILE = "F"
SOFT_SWITCH = "o"
HEAVY_SWITCH = "X"
BRIDGE_OFF = "b"
BRIDGE_ON = "B"
LOCK_STANDING = "S"
LOCK_LYING_X = "="
LOCK_LYING_Y = "H"
KEY = "K"
GATE = "#"
SPIN = "@"   # mystery spin tile: the first landing moves the goal to "g" (and spins the view)

LOCK_SYMBOLS = {LOCK_STANDING: STANDING, LOCK_LYING_X: LYING_X, LOCK_LYING_Y: LYING_Y}
SWITCH_SYMBOLS = (SOFT_SWITCH, HEAVY_SWITCH)
BRIDGE_SYMBOLS = (BRIDGE_OFF, BRIDGE_ON)


class Outcome(Enum):
    """What happened after the block made a move."""

    MOVED = "moved"
    FELL = "fell"
    WON = "won"


class Lock:
    """A keyhole that is solved when the block rests on it in one exact pose."""

    def __init__(self, colour, pose, x, y):
        self.colour = colour
        self.pose = pose
        # The cells a correctly placed block covers, e.g. 2 cells for a lying lock.
        self.cells = Block(x, y, pose).cells()

    def fits(self, block):
        """Return True if the block is resting on this lock in the right pose."""
        return block.pose == self.pose and block.cells() == self.cells


class Key:
    """A key that appears once its lock is solved and opens gates of its colour."""

    def __init__(self, colour, x, y):
        self.colour = colour
        self.cell = (x, y)


class Switch:
    """A switch that toggles a set of bridge cells when pressed.

    A soft switch is pressed by any part of the block. A heavy switch is only
    pressed by a standing block.
    """

    def __init__(self, x, y, heavy, bridge_cells):
        self.cell = (x, y)
        self.heavy = heavy
        self.bridge_cells = tuple(bridge_cells)

    def is_pressed_by(self, block):
        """Return True if the block is pressing this switch."""
        if self.heavy:
            return block.pose == STANDING and block.cells()[0] == self.cell
        return self.cell in block.cells()


class Board:
    """A level's tiles plus the state that changes during play.

    The changing state is which bridges are on, which locks are solved,
    which keys have been collected and which goal is open. Gates of a colour
    are open once that colour's key is collected.
    """

    def __init__(self, name, grid, start, locks, keys, gates, switches):
        """Create a board. Normally done by level_loader.load_level().

        grid     - list of strings, one per row, using the tile symbols above
        start    - (x, y) where the block starts standing
        locks    - list of Lock
        keys     - dict of colour -> Key
        gates    - dict of colour -> list of (x, y) gate cells
        switches - dict of (x, y) -> Switch
        """
        self.name = name
        self.grid = grid
        self.start = start
        self.locks = locks
        self.keys = keys
        self.gates = gates
        self.switches = switches
        self.reset()

    # ----- state -----

    def reset(self):
        """Put the board back to how the level starts."""
        self.bridges_on = frozenset(
            (x, y)
            for y, row in enumerate(self.grid)
            for x, symbol in enumerate(row)
            if symbol == BRIDGE_ON
        )
        self.solved_locks = frozenset()
        self.collected_keys = frozenset()
        self.goals_swapped = False   # True once a spin tile has been used and opened the "g" goal

    def start_block(self):
        """Return the block in its starting position."""
        return Block(self.start[0], self.start[1], STANDING)

    def get_state(self):
        """Return the changing state as a hashable tuple (used by the solver)."""
        return (self.bridges_on, self.solved_locks, self.collected_keys, self.goals_swapped)

    def set_state(self, state):
        """Restore a state previously returned by get_state()."""
        self.bridges_on, self.solved_locks, self.collected_keys, self.goals_swapped = state

    # ----- tiles -----

    def tile(self, x, y):
        """Return the tile symbol at (x, y), or VOID outside the grid."""
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]):
            return self.grid[y][x]
        return VOID

    def width(self):
        """Number of columns in the widest row of the grid."""
        return max((len(row) for row in self.grid), default=0)

    def height(self):
        """Number of rows in the grid."""
        return len(self.grid)

    def gate_colour(self, cell):
        """Return the colour of the gate at cell, or None if it isn't a gate."""
        for colour, cells in self.gates.items():
            if cell in cells:
                return colour
        return None

    def spin_cells(self, block):
        """Return the spin tiles the block is resting on."""
        return [cell for cell in block.cells() if self.tile(*cell) == SPIN]

    def open_goal(self):
        """Return the symbol of the goal that is currently open: "G" or "g"."""
        return GOAL_ALT if self.goals_swapped else GOAL

    def goal_cells(self):
        """Return every goal spot, open or sealed, as {cell: symbol}."""
        return {
            (x, y): symbol
            for y, row in enumerate(self.grid)
            for x, symbol in enumerate(row)
            if symbol in (GOAL, GOAL_ALT)
        }

    def key_visible(self, colour):
        """Return True if the key of this colour is showing and not yet collected."""
        return colour in self.solved_locks and colour not in self.collected_keys

    def is_solid(self, x, y):
        """Return True if the cell can hold the block up."""
        symbol = self.tile(x, y)
        if symbol == VOID:
            return False
        if symbol in BRIDGE_SYMBOLS:
            return (x, y) in self.bridges_on
        if symbol == GATE:
            return self.gate_colour((x, y)) in self.collected_keys
        return True

    def supports(self, block):
        """Return True if the block is safely resting on the board."""
        cells = block.cells()
        if not all(self.is_solid(x, y) for x, y in cells):
            return False
        # A fragile tile breaks under the full weight of a standing block.
        if block.pose == STANDING and self.tile(*cells[0]) == FRAGILE:
            return False
        return True

    # ----- moves -----

    def step(self, block, direction):
        """Roll the block one step and apply what it lands on.

        Returns (new_block, Outcome). The board's state is updated in place.
        """
        new_block = block.roll(direction)
        if not self.supports(new_block):
            return new_block, Outcome.FELL

        self._press_switches(new_block)
        self._check_locks(new_block)
        self._collect_keys(new_block)
        if self.spin_cells(new_block) and not self.goals_swapped:
            # A spin tile works once: it seals "G" and opens "g" for the rest of the attempt.
            self.goals_swapped = True

        # A switch may have just removed the bridge the block is on.
        if not self.supports(new_block):
            return new_block, Outcome.FELL

        if new_block.pose == STANDING and self.tile(new_block.x, new_block.y) == self.open_goal():
            return new_block, Outcome.WON
        return new_block, Outcome.MOVED

    def _press_switches(self, block):
        """Toggle the bridges of every switch the block presses on this landing."""
        bridges = set(self.bridges_on)
        for cell in block.cells():
            switch = self.switches.get(cell)
            if switch is not None and switch.is_pressed_by(block):
                # Toggle each linked bridge cell.
                bridges ^= set(switch.bridge_cells)
        self.bridges_on = frozenset(bridges)

    def _check_locks(self, block):
        """Mark a lock as solved when the block rests on it in the lock's pose."""
        for lock in self.locks:
            if lock.colour not in self.solved_locks and lock.fits(block):
                self.solved_locks = self.solved_locks | {lock.colour}

    def _collect_keys(self, block):
        """Pick up any visible key the block is touching."""
        for colour, key in self.keys.items():
            if self.key_visible(colour) and key.cell in block.cells():
                self.collected_keys = self.collected_keys | {colour}
