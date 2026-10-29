"""The Game class: runs the levels, handles input and switches between states."""

import math
import random

import pygame

from boxlox import board as b
from boxlox.block import UP, DOWN, LEFT, RIGHT, STANDING
from boxlox.board import Outcome
from boxlox.effects import Effects
from boxlox.overlay import game_over_overlay, you_win_overlay, title_screen, pause_overlay
from boxlox.title_scene import TitleScene
from boxlox.renderer import Renderer, COLOURS, BRIDGE_COLOUR, FRAGILE_COLOUR, GOAL_GLOW, BLOCK_COLOUR, SPIN_COLOUR

# Game states
TITLE = "TITLE"           # title screen showing
PLAYING = "PLAYING"       # waiting for an arrow key
ROLLING = "ROLLING"       # block tipping over to its new spot
SPINNING = "SPINNING"     # the view turning 90 degrees after a spin tile; input ignored
FALLING = "FALLING"       # block dropping off the board; input ignored
FAILED = "FAILED"         # GAME OVER screen showing
GOAL_DROP = "GOAL_DROP"   # block sinking through the goal hole; input ignored
COMPLETE = "COMPLETE"     # YOU WIN! screen showing

ROLL_TIME = 0.16          # seconds for one roll
FALL_TIME = 0.5           # seconds for the block to drop off screen
FALL_GRAVITY = 90.0       # height units per second squared
GOAL_DROP_TIME = 0.7      # seconds for the block to sink into the hole
GOAL_PAUSE = 0.4          # pause after the block disappears
RISE_TIME = 0.35          # seconds for a gate or bridge to rise into place
CARD_TIME = 1.8           # seconds the "LEVEL n" title stays up
PAUSE_KEYS = (pygame.K_ESCAPE, pygame.K_p)
SPIN_TIME = 0.6           # seconds for the view to turn 90 degrees

ARROW_KEYS = {
    pygame.K_UP: UP,
    pygame.K_DOWN: DOWN,
    pygame.K_LEFT: LEFT,
    pygame.K_RIGHT: RIGHT,
}


class Game:
    """Owns the current level and block, and moves between game states."""

    def __init__(self, screen, levels):
        self.screen = screen
        self.levels = levels
        self.renderer = Renderer(screen)
        self.effects = Effects(self.renderer.s)
        self.title_scene = TitleScene(screen)
        self.time = 0.0
        self.pause_menu = None      # the PAUSED screen while the game is paused
        s = self.renderer.s
        size = round(40 * s)
        self.pause_button = pygame.Rect(screen.get_width() - size - round(16 * s), round(14 * s), size, size)
        self.load_level(0)
        self.set_state(TITLE)

    def load_level(self, index):
        """Start (or restart) the level at the given index.

        Everything starts fresh, including spin tiles, which hide again.
        """
        self.level_index = index
        self.board = self.levels[index]
        self.board.reset()
        self.block = self.board.start_block()
        self.renderer.centre_on(self.board)
        self.view_turns = 0         # how many quarter turns the view has made
        self.renderer.set_view_angle(0.0)
        self.roll = None            # details of the roll in progress
        self.queued = None          # an arrow pressed mid-roll, played next
        self.hidden = set()         # cells not drawn (broken ice)
        self.revealed = set()       # spin tiles set off on this attempt
        self.rising = {}            # cell -> time it started rising into place
        self.card_time = 0.0
        self.pause_menu = None
        self.effects.clear()
        self.set_state(PLAYING)

    def set_state(self, state):
        """Switch to a new state and restart the state's timer."""
        self.state = state
        self.state_time = 0.0
        self.overlay = None
        size = self.screen.get_size()
        if state == TITLE:
            self.overlay = title_screen(size)
        elif state == FAILED:
            self.overlay = game_over_overlay(size)
        elif state == COMPLETE:
            self.overlay = you_win_overlay(size)

    # ----- input -----

    def can_pause(self):
        """The game can be paused any time a level is on screen and no menu is showing."""
        return self.overlay is None and self.pause_menu is None

    def handle_event(self, event):
        """Handle one Pygame event. Returns False if the game should quit."""
        if self.pause_menu is not None:
            action = self.pause_menu.handle_event(event)
            if action == "quit":
                return False
            if action == "resume":
                self.pause_menu = None
            return True

        if self.overlay is not None:
            action = self.overlay.handle_event(event)
            if action == "quit":
                return False
            if action == "restart":
                self.load_level(self.level_index)
            elif action in ("play", "play_again"):
                self.load_level(0)
            return True

        clicked_pause = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                         and self.pause_button.collidepoint(event.pos))
        if (event.type == pygame.KEYDOWN and event.key in PAUSE_KEYS) or clicked_pause:
            self.pause_menu = pause_overlay(self.screen.get_size())
            return True

        if event.type == pygame.KEYDOWN and event.key in ARROW_KEYS:
            direction = self.screen_to_grid(ARROW_KEYS[event.key])
            if self.state == PLAYING:
                self.start_move(direction)
            elif self.state == ROLLING:
                self.queued = direction
        return True

    def screen_to_grid(self, direction):
        """Turn an arrow key's on-screen direction into a grid direction.

        After the view has turned, "right on screen" is a different way across
        the grid, so the direction is turned back by the same amount.
        """
        dx, dy = direction
        for _ in range(self.view_turns):
            dx, dy = dy, -dx  # undo one quarter turn
        return (dx, dy)

    def start_move(self, direction):
        """Work out the move straight away, then animate it."""
        before = self.board.get_state()
        old_block = self.block
        self.block, outcome = self.board.step(old_block, direction)
        self.roll = (old_block, direction, outcome, before)
        self.set_state(ROLLING)

    def finish_move(self):
        """Called when the roll animation ends: show effects and move on."""
        _, _, outcome, before = self.roll
        self.roll = None
        # (before is the board state from before the move; before[3] = goals swapped)
        self.spawn_effects(before, outcome)

        if outcome is Outcome.FELL:
            self.queued = None
            self.set_state(FALLING)
        elif outcome is Outcome.WON:
            self.queued = None
            self.effects.burst(self.cell_point(self.block.cells()[0], 0.2), GOAL_GLOW, count=40)
            self.set_state(GOAL_DROP)
        elif self.board.goals_swapped != before[3]:
            # A spin tile just went off: reveal it for good, move the goal and turn the view.
            self.queued = None
            for cell in self.board.spin_cells(self.block):
                self.revealed.add(cell)
                self.effects.burst(self.cell_point(cell, 0.3), SPIN_COLOUR, count=30)
            self.set_state(SPINNING)
        else:
            self.set_state(PLAYING)
            if self.queued is not None:
                direction, self.queued = self.queued, None
                self.start_move(direction)

    # ----- effects -----

    def cell_point(self, cell, z=0.0):
        """Screen point above the centre of a cell."""
        return self.renderer.project(cell[0] + 0.5, cell[1] + 0.5, z)

    def spawn_effects(self, before, outcome):
        """Compare the board before and after a move and celebrate what changed."""
        bridges_before, locks_before, keys_before, swapped_before = before
        board = self.board

        for lock in board.locks:
            if lock.colour in board.solved_locks and lock.colour not in locks_before:
                colour = COLOURS[lock.colour]
                for cell in lock.cells:
                    self.effects.burst(self.cell_point(cell, 0.3), colour, count=24)
                self.effects.burst(self.cell_point(board.keys[lock.colour].cell, 0.7), colour, count=18)

        for colour in board.collected_keys - keys_before:
            self.effects.burst(self.cell_point(board.keys[colour].cell, 0.7), COLOURS[colour], count=30)
            for cell in board.gates.get(colour, []):
                self.rising[cell] = self.time
                self.effects.burst(self.cell_point(cell), COLOURS[colour], count=12)

        for cell in board.bridges_on ^ bridges_before:
            if cell in board.bridges_on:
                self.rising[cell] = self.time
            self.effects.burst(self.cell_point(cell), BRIDGE_COLOUR, count=10, size=(2, 4))

        if board.goals_swapped != swapped_before:
            # The goal moved: puff where it closed, sparkle where it opened.
            for cell, symbol in board.goal_cells().items():
                opened = symbol == board.open_goal()
                self.effects.burst(self.cell_point(cell, 0.2), GOAL_GLOW if opened else SPIN_COLOUR,
                                   count=40 if opened else 20)

        if outcome is Outcome.FELL:
            self.effects.shake(8, 0.35)
            cell = self.block.cells()[0]
            if self.block.pose == STANDING and board.tile(*cell) == b.FRAGILE:
                self.hidden.add(cell)
                self.effects.chunks(self.cell_point(cell), FRAGILE_COLOUR)

    def tile_rise(self):
        """Return {cell: z offset} for gates and bridges still rising into place."""
        offsets = {}
        for cell, started in list(self.rising.items()):
            progress = (self.time - started) / RISE_TIME
            if progress >= 1:
                del self.rising[cell]
            else:
                offsets[cell] = -1.2 * (1 - progress) ** 2
        return offsets

    # ----- update -----

    def update(self, dt):
        """Advance timers and animations by dt seconds."""
        if self.pause_menu is not None:
            return  # paused: everything stays exactly where it is
        self.time += dt
        self.state_time += dt
        self.card_time += dt
        self.effects.update(dt)
        if self.state == TITLE:
            self.title_scene.update(dt)

        if self.state == ROLLING and self.state_time >= ROLL_TIME:
            self.finish_move()
        elif self.state == SPINNING and self.state_time >= SPIN_TIME:
            self.view_turns = (self.view_turns + 1) % 4
            self.set_state(PLAYING)
        elif self.state == FALLING and self.state_time >= FALL_TIME:
            self.set_state(FAILED)
        elif self.state == GOAL_DROP and self.state_time >= GOAL_DROP_TIME + GOAL_PAUSE:
            if self.level_index + 1 < len(self.levels):
                self.load_level(self.level_index + 1)
            else:
                self.set_state(COMPLETE)
        elif self.state == COMPLETE and random.random() < dt * 30:
            colours = list(COLOURS.values()) + [BLOCK_COLOUR, GOAL_GLOW]
            self.effects.confetti(self.screen.get_width(), colours)

    def block_height(self):
        """How far the block has dropped below its resting height."""
        if self.state in (FALLING, FAILED):
            t = min(self.state_time, FALL_TIME) if self.state == FALLING else FALL_TIME
            return -0.5 * FALL_GRAVITY * t * t
        if self.state in (GOAL_DROP, COMPLETE):
            progress = min(self.state_time / GOAL_DROP_TIME, 1.0) if self.state == GOAL_DROP else 1.0
            return -2.0 * progress * progress  # speeds up as it sinks
        return 0.0

    # ----- draw -----

    def draw(self):
        """Draw the current frame: title, or level plus HUD, effects and any menus."""
        if self.state == TITLE:
            self.title_scene.draw()
            self.overlay.draw(self.screen, self.time)
            return

        self.renderer.offset = self.effects.offset()
        turns = self.view_turns
        if self.state == SPINNING:
            progress = min(self.state_time / SPIN_TIME, 1.0)
            turns += progress * progress * (3 - 2 * progress)
        self.renderer.set_view_angle(turns * math.pi / 2)

        block, roll = self.block, None
        if self.state == ROLLING:
            old_block, direction, _, _ = self.roll
            progress = min(self.state_time / ROLL_TIME, 1.0)
            eased = progress * progress * (3 - 2 * progress)  # smooth start and finish
            block, roll = old_block, (self.block, direction, eased)

        sinking = self.state in (GOAL_DROP, COMPLETE)
        self.renderer.draw(
            self.board,
            block,
            self.time,
            block_z=self.block_height(),
            clip_floor=sinking,
            show_block=self.state != FAILED,
            roll=roll,
            hidden=self.hidden,
            tile_rise=self.tile_rise(),
            revealed=self.revealed,
        )
        self.effects.draw(self.screen)
        self.renderer.draw_hud(self.level_index + 1, len(self.levels), self.board)
        if self.can_pause():
            hovered = self.pause_button.collidepoint(pygame.mouse.get_pos())
            self.renderer.draw_pause_button(self.pause_button, hovered)

        if self.card_time < CARD_TIME and self.state in (PLAYING, ROLLING, SPINNING):
            # Fade in quickly, hold, then fade out.
            fade = min(self.card_time / 0.25, 1.0, (CARD_TIME - self.card_time) / 0.5)
            self.renderer.draw_level_card(self.level_index + 1, self.board.name, int(255 * fade))
        if self.overlay is not None:
            self.overlay.draw(self.screen, self.time)
        if self.pause_menu is not None:
            self.pause_menu.draw(self.screen, self.time)
