"""The 1x1x2 block the player rolls around the board."""

from dataclasses import dataclass

# Block poses
STANDING = "STANDING"   # upright, covers 1 cell
LYING_X = "LYING_X"     # lying east-west, covers (x, y) and (x+1, y)
LYING_Y = "LYING_Y"     # lying north-south, covers (x, y) and (x, y+1)

# Directions as (dx, dy). y grows downwards, so UP is north.
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
DIRECTIONS = (UP, DOWN, LEFT, RIGHT)


@dataclass(frozen=True)
class Block:
    """An immutable block position and pose.

    (x, y) is always the top-left cell the block covers. Rolling returns a
    new Block rather than changing this one, which keeps the solver simple.
    """

    x: int
    y: int
    pose: str = STANDING

    def cells(self):
        """Return the grid cells the block is resting on."""
        if self.pose == STANDING:
            return ((self.x, self.y),)
        if self.pose == LYING_X:
            return ((self.x, self.y), (self.x + 1, self.y))
        return ((self.x, self.y), (self.x, self.y + 1))

    def roll(self, direction):
        """Return the block after rolling one step in the given direction."""
        dx, dy = direction
        x, y = self.x, self.y

        if self.pose == STANDING:
            # Tip over onto the two cells next to us in that direction.
            if direction == RIGHT:
                return Block(x + 1, y, LYING_X)
            if direction == LEFT:
                return Block(x - 2, y, LYING_X)
            if direction == DOWN:
                return Block(x, y + 1, LYING_Y)
            return Block(x, y - 2, LYING_Y)

        if self.pose == LYING_X:
            if direction == RIGHT:
                return Block(x + 2, y, STANDING)
            if direction == LEFT:
                return Block(x - 1, y, STANDING)
            # Rolling sideways keeps it lying east-west.
            return Block(x, y + dy, LYING_X)

        # LYING_Y
        if direction == DOWN:
            return Block(x, y + 2, STANDING)
        if direction == UP:
            return Block(x, y - 1, STANDING)
        return Block(x + dx, y, LYING_Y)
