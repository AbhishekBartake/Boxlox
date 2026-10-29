"""Check that every level in the levels folder can be solved.

Run with:  python check_levels.py

Prints the shortest solution for each level (U/D/L/R = up/down/left/right),
or UNSOLVABLE. Directions are as the board looks before any spin tile turns
the view; after a spin, the arrow keys to press are turned too. Exits with an error code if any level fails, so it can be
used as a quick test after editing a level file.
"""

import os
import sys
import time

from boxlox.level_loader import load_all_levels, LevelError
from boxlox.solver import Solver, moves_to_text

LEVELS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")


def main():
    """Solve every level and print the results. Exit with code 1 if any level is unsolvable."""
    try:
        levels = load_all_levels(LEVELS_FOLDER)
    except LevelError as error:
        sys.exit(f"Could not load the levels: {error}")

    all_solvable = True
    for number, board in enumerate(levels, start=1):
        started = time.perf_counter()
        moves = Solver(board).solve()
        seconds = time.perf_counter() - started

        if moves is None:
            all_solvable = False
            print(f"Level {number} {board.name!r}: UNSOLVABLE")
        else:
            print(f"Level {number} {board.name!r}: solvable in {len(moves)} moves "
                  f"({moves_to_text(moves)}) [{seconds:.2f}s]")

    if not all_solvable:
        sys.exit(1)


if __name__ == "__main__":
    main()
