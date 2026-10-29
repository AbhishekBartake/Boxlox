"""A recursive solver that finds the shortest way to finish a level.

It does a depth-first search: from the current position it tries each of the
four rolls, and for every roll that doesn't fall it calls itself again from
the new position. Two rules keep the search fast:

- If a position (block + board state) has already been reached in the same
  number of moves or fewer, there's no point exploring it again.
- Once a solution is found, any path that can't beat it is abandoned.
"""

from boxlox.block import UP, DOWN, LEFT, RIGHT, DIRECTIONS
from boxlox.board import Outcome

MAX_MOVES = 200   # stays well under Python's default recursion limit of 1000

DIRECTION_NAMES = {UP: "U", DOWN: "D", LEFT: "L", RIGHT: "R"}


class Solver:
    """Searches a Board for the shortest sequence of moves to the goal."""

    def __init__(self, board, max_moves=MAX_MOVES):
        self.board = board
        self.max_moves = max_moves
        self.best = None        # shortest list of directions found so far
        self.fewest_moves = {}  # (block, state) -> fewest moves it took to reach it

    def solve(self, block=None):
        """Return the shortest list of directions from block to the goal.

        Starts from the level's start position if no block is given. Returns
        None if the level can't be solved within max_moves. The board's state
        is left exactly as it was.
        """
        if block is None:
            block = self.board.start_block()
        saved_state = self.board.get_state()
        self.best = None
        self.fewest_moves = {(block, saved_state): 0}

        self._search(block, saved_state, [])

        self.board.set_state(saved_state)
        return self.best

    def _search(self, block, state, path):
        """Try every roll from this position, recursing into the ones that land safely."""
        moves_so_far = len(path) + 1
        for direction in DIRECTIONS:
            self.board.set_state(state)
            new_block, outcome = self.board.step(block, direction)

            # Base case 1: this roll finishes the level. Keep it if it's the shortest so far.
            if outcome is Outcome.WON:
                if self.best is None or moves_so_far < len(self.best):
                    self.best = path + [direction]
                continue
            # Base case 2: the block fell, so this roll leads nowhere.
            if outcome is Outcome.FELL:
                continue

            # Prune: too long, can't beat the best solution, or already reached faster.
            if moves_so_far >= self.max_moves:
                continue
            if self.best is not None and moves_so_far + 1 >= len(self.best):
                continue
            position = (new_block, self.board.get_state())
            if self.fewest_moves.get(position, self.max_moves + 1) <= moves_so_far:
                continue
            self.fewest_moves[position] = moves_so_far

            # Recursive case: carry on searching from the new position, then
            # undo the move (backtrack) so the next direction starts clean.
            path.append(direction)
            self._search(new_block, position[1], path)
            path.pop()


def moves_to_text(moves):
    """Turn a list of directions into a short string like 'RRDL'."""
    return "".join(DIRECTION_NAMES[direction] for direction in moves)
