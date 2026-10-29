"""BOXLOX - roll the block, turn the locks, drop into the goal.

Run with:  python main.py
"""

import os
import sys

try:
    import pygame
except ImportError:
    sys.exit("BOXLOX needs Pygame. Install it with:  python -m pip install pygame")

from boxlox.display import setup_window_scale, window_size
from boxlox.game import Game
from boxlox.level_loader import load_all_levels, LevelError

FPS = 60
LEVELS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")


def main():
    """Load the levels, open the window and run the game loop until the player quits."""
    try:
        levels = load_all_levels(LEVELS_FOLDER)
    except LevelError as error:
        sys.exit(f"Could not load the levels: {error}")

    # On high-resolution screens, open a bigger window and draw everything
    # bigger, instead of letting Windows blur a small window up to size.
    scale = setup_window_scale()
    pygame.init()
    screen = pygame.display.set_mode(window_size(scale))
    pygame.display.set_caption("BOXLOX")
    clock = pygame.time.Clock()
    game = Game(screen, levels)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT or not game.handle_event(event):
                running = False
        game.update(dt)
        game.draw()
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
