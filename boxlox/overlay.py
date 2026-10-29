"""Pop-up screens: the title screen, GAME OVER and YOU WIN!

All sizes below are for the 960x640 design size; they are multiplied by
the window's scale so everything stays sharp on high-resolution screens.
"""

import math

import pygame

from boxlox.display import scale_of


def shade(colour, factor):
    """Return the colour made darker (factor < 1) or lighter (factor > 1)."""
    return tuple(max(0, min(255, int(channel * factor))) for channel in colour)

BUTTON_W = 200
BUTTON_H = 54
BUTTON_GAP = 30

DIM_COLOUR = (8, 8, 16, 170)
TITLE_COLOUR = (245, 245, 250)
BUTTON_TEXT_COLOUR = (245, 245, 250)
KEY_HINT_COLOUR = (170, 176, 196)

# The main button (Play, Restart, Play Again): a blue-to-violet gradient.
PRIMARY_LEFT = (74, 128, 246)
PRIMARY_RIGHT = (146, 94, 234)
PRIMARY_BORDER = (196, 204, 255)
PRIMARY_GLOW = (120, 110, 255)

# Other buttons (Quit): a quiet slate colour.
SECONDARY_COLOUR = (56, 62, 82)
SECONDARY_HOVER = (70, 77, 100)
SECONDARY_BORDER = (100, 108, 134)
SECONDARY_GLOW = (120, 130, 160)


class Button:
    """A clickable button that can also be pressed with keyboard keys."""

    def __init__(self, label, action, keys, key_hint):
        self.label = label
        self.action = action
        self.keys = keys
        self.key_hint = key_hint
        self.rect = pygame.Rect(0, 0, BUTTON_W, BUTTON_H)
        self.primary = False   # the first button of each screen is made the main one
        self.glow = 0.0        # 0 = no hover glow, 1 = full glow; eases in and out


class Overlay:
    """A dimmed screen with a title and a row of buttons.

    handle_event() returns the chosen button's action (e.g. "restart" or
    "quit"), or None if nothing was chosen.
    """

    def __init__(self, screen_size, title, buttons, title_colour=TITLE_COLOUR):
        self.title = title
        self.buttons = buttons
        self.title_colour = title_colour
        self.s = s = scale_of(screen_size)
        self.title_font = pygame.font.Font(None, round(96 * s))
        self.button_font = pygame.font.Font(None, round(36 * s))
        self.hint_font = pygame.font.Font(None, round(22 * s))

        width, height = screen_size
        button_w, gap = round(BUTTON_W * s), round(BUTTON_GAP * s)
        total = len(buttons) * button_w + (len(buttons) - 1) * gap
        left = (width - total) // 2
        for i, button in enumerate(buttons):
            button.rect = pygame.Rect(left + i * (button_w + gap), height // 2 + round(30 * s),
                                      button_w, round(BUTTON_H * s))
            button.primary = i == 0
        self._surfaces = {}   # cached gradient and glow pictures

    def handle_event(self, event):
        """Return the action of a button chosen by key or click, otherwise None."""
        if event.type == pygame.KEYDOWN:
            for button in self.buttons:
                if event.key in button.keys:
                    return button.action
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button.rect.collidepoint(event.pos):
                    return button.action
        return None

    def draw(self, screen, time=0.0):
        """Dim the screen behind, then draw the title and the buttons."""
        width, height = screen.get_size()
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill(DIM_COLOUR)
        screen.blit(dim, (0, 0))
        self.draw_title(screen, time)
        self.draw_buttons(screen)

    def draw_title(self, screen, time):
        """Draw the overlay's title, gently pulsing in size."""
        width, height = screen.get_size()
        s = self.s
        # A gentle pulse in size makes the title feel alive.
        pulse = 1 + 0.03 * math.sin(time * 3)
        for offset, colour in (((4 * s, 5 * s), (0, 0, 0)), ((0, 0), self.title_colour)):
            title = self.title_font.render(self.title, True, colour)
            size = (int(title.get_width() * pulse), int(title.get_height() * pulse))
            title = pygame.transform.smoothscale(title, size)
            centre = (width // 2 + offset[0], height // 2 - 50 * s + offset[1])
            screen.blit(title, title.get_rect(center=centre))

    def _gradient(self, size, radius, brightness):
        """A rounded button face shading from blue on the left to violet on the right."""
        key = ("gradient", size, brightness)
        if key not in self._surfaces:
            width, height = size
            face = pygame.Surface(size, pygame.SRCALPHA)
            for x in range(width):
                amount = x / max(1, width - 1)
                colour = [int((a + (c - a) * amount) * brightness) for a, c in zip(PRIMARY_LEFT, PRIMARY_RIGHT)]
                pygame.draw.line(face, [min(255, v) for v in colour], (x, 0), (x, height))
            # A soft lighter band across the top half gives it a little shine.
            shine = pygame.Surface((width, height // 2), pygame.SRCALPHA)
            shine.fill((255, 255, 255, 28))
            face.blit(shine, (0, 0))
            mask = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            face.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self._surfaces[key] = face
        return self._surfaces[key]

    def _glow(self, size, radius, colour):
        """A soft blurred halo slightly bigger than the button."""
        key = ("glow", size, colour)
        if key not in self._surfaces:
            spread = round(16 * self.s)
            width, height = size[0] + spread * 2, size[1] + spread * 2
            halo = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.draw.rect(halo, (*colour, 255), (spread // 2, spread // 2, width - spread, height - spread),
                             border_radius=radius + spread // 2)
            small = pygame.transform.smoothscale(halo, (max(1, width // 8), max(1, height // 8)))
            self._surfaces[key] = pygame.transform.smoothscale(small, (width, height))
        return self._surfaces[key]

    def draw_buttons(self, screen):
        """Draw every button, glowing when the mouse hovers over it."""
        s = self.s
        radius = round(10 * s)
        mouse = pygame.mouse.get_pos()
        for button in self.buttons:
            hovered = button.rect.collidepoint(mouse)
            # Ease the glow in and out instead of snapping.
            button.glow += ((1.0 if hovered else 0.0) - button.glow) * 0.18
            size = button.rect.size

            if button.glow > 0.02:
                halo = self._glow(size, radius, PRIMARY_GLOW if button.primary else SECONDARY_GLOW).copy()
                halo.set_alpha(int((150 if button.primary else 80) * button.glow))
                screen.blit(halo, halo.get_rect(center=button.rect.center))

            pygame.draw.rect(screen, (0, 0, 0), button.rect.move(0, round(4 * s)), border_radius=radius)
            if button.primary:
                screen.blit(self._gradient(size, radius, 1.15 if hovered else 1.0), button.rect)
                border = PRIMARY_BORDER
            else:
                pygame.draw.rect(screen, SECONDARY_HOVER if hovered else SECONDARY_COLOUR, button.rect, border_radius=radius)
                border = SECONDARY_BORDER
            pygame.draw.rect(screen, border, button.rect, max(1, round(2 * s)), border_radius=radius)
            label = self.button_font.render(button.label, True, BUTTON_TEXT_COLOUR)
            screen.blit(label, label.get_rect(center=button.rect.center))
            hint = self.hint_font.render(button.key_hint, True, KEY_HINT_COLOUR)
            screen.blit(hint, hint.get_rect(midtop=(button.rect.centerx, button.rect.bottom + round(8 * s))))


class TitleScreen(Overlay):
    """The BOXLOX title screen: a chunky 3D logo and Play/Quit buttons.

    No dimming: the moving TitleScene is drawn behind it by the game.
    """

    LETTER_COLOURS = ((236, 180, 86), (236, 180, 86), (236, 180, 86),
                      (232, 70, 70), (70, 132, 240), (66, 192, 102))
    LOGO_TOP = 40         # design-size y of the top of the letters
    SUBTITLE_Y = 428
    BUTTONS_Y = 462

    def __init__(self, screen_size):
        super().__init__(screen_size, "BOXLOX", [
            Button("Play", "play", (pygame.K_RETURN, pygame.K_SPACE), "Enter / Space"),
            Button("Quit", "quit", (pygame.K_q, pygame.K_ESCAPE), "Q / Esc"),
        ])
        s = self.s
        self.logo_font = pygame.font.Font(None, round(176 * s))
        self.subtitle_font = pygame.font.Font(None, round(34 * s))
        for button in self.buttons:
            button.rect.y = round(self.BUTTONS_Y * s)
        # Build each 3D letter once; drawing them is then just a blit.
        self.letters = [self._build_letter(letter, colour)
                        for letter, colour in zip(self.title, self.LETTER_COLOURS)]

    def _build_letter(self, letter, colour):
        """Return (surface, face_offset, face_width) for one chunky 3D letter.

        Layers, back to front: a soft blurred shadow, a dark outline around
        every edge, an extruded side going down-right, and a face shaded
        from light at the top to darker at the bottom.
        """
        s = self.s
        depth = max(3, round(10 * s))      # how far the letter sticks out
        ring = max(2, round(4 * s))        # outline thickness
        margin = ring + 2
        white = self.logo_font.render(letter, True, (255, 255, 255))
        black = self.logo_font.render(letter, True, (12, 10, 22))
        side = self.logo_font.render(letter, True, shade(colour, 0.5))
        w, h = white.get_size()
        shadow_drop = round(10 * s)
        surface = pygame.Surface((w + 2 * margin + depth + shadow_drop * 2, h + 2 * margin + depth + shadow_drop * 2),
                                 pygame.SRCALPHA)

        # Soft shadow: shrink and re-grow the dark letter to blur it.
        small = pygame.transform.smoothscale(black, (max(1, w // 6), max(1, h // 6)))
        blurred = pygame.transform.smoothscale(small, (w + depth, h + depth))
        blurred.set_alpha(150)
        surface.blit(blurred, (margin + depth // 2 + shadow_drop, margin + depth // 2 + shadow_drop))

        # Dark outline around the face and the whole extruded side.
        ring_offsets = [(round(ring * math.cos(a)), round(ring * math.sin(a)))
                        for a in (i * math.tau / 16 for i in range(16))]
        for i in range(depth + 1):
            for dx, dy in ring_offsets:
                surface.blit(black, (margin + i + dx, margin + i + dy))

        # Extruded side, darker towards the back.
        for i in range(depth, 0, -1):
            layer = side.copy()
            layer.fill((*shade((255, 255, 255), 0.75 + 0.25 * (1 - i / depth)), 255), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(layer, (margin + i, margin + i))

        # Face: a vertical gradient from light to the letter colour, then a thin top shine.
        gradient = pygame.Surface((w, h), pygame.SRCALPHA)
        top_colour, bottom_colour = shade(colour, 1.3), shade(colour, 0.88)
        for y in range(h):
            amount = y / max(1, h - 1)
            gradient.fill((*[int(a + (c - a) * amount) for a, c in zip(top_colour, bottom_colour)], 255),
                          (0, y, w, 1))
        face = white.copy()
        face.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(face, (margin, margin))
        return surface, margin, w

    def draw(self, screen, time=0.0):
        """Draw the logo and the buttons (the scene behind is drawn by TitleScene)."""
        self.draw_title(screen, time)
        self.draw_buttons(screen)

    def draw_title(self, screen, time):
        """Draw the 3D BOXLOX logo and its subtitle."""
        width, height = screen.get_size()
        s = self.s
        gap = round(4 * s)
        total = sum(face_w for _, _, face_w in self.letters) + gap * (len(self.letters) - 1)
        x = (width - total) / 2
        for i, (surface, margin, face_w) in enumerate(self.letters):
            # Each letter bobs on a wave, a little behind the one before it.
            y = self.LOGO_TOP * s + 8 * s * math.sin(time * 2.5 - i * 0.6)
            screen.blit(surface, (x - margin, y - margin))
            x += face_w + gap

        centre = (width // 2, round(self.SUBTITLE_Y * s))
        for offset, colour in (((round(2 * s), round(2 * s)), (0, 0, 0)), ((0, 0), TITLE_COLOUR)):
            subtitle = self.subtitle_font.render("Roll the block.  Fit the locks.  Drop into the hole.", True, colour)
            screen.blit(subtitle, subtitle.get_rect(center=(centre[0] + offset[0], centre[1] + offset[1])))


def game_over_overlay(screen_size):
    """The screen shown after the block falls."""
    return Overlay(screen_size, "GAME OVER", [
        Button("Restart", "restart", (pygame.K_r, pygame.K_RETURN), "R / Enter"),
        Button("Quit", "quit", (pygame.K_q, pygame.K_ESCAPE), "Q / Esc"),
    ], title_colour=(240, 90, 90))


def you_win_overlay(screen_size):
    """The screen shown after the last level is finished."""
    return Overlay(screen_size, "YOU WIN!", [
        Button("Play Again", "play_again", (pygame.K_r, pygame.K_RETURN), "R / Enter"),
        Button("Quit", "quit", (pygame.K_q, pygame.K_ESCAPE), "Q / Esc"),
    ], title_colour=(250, 210, 80))


def pause_overlay(screen_size):
    """The screen shown when the player pauses with Esc, P or the pause button."""
    return Overlay(screen_size, "PAUSED", [
        Button("Resume", "resume", (pygame.K_ESCAPE, pygame.K_p, pygame.K_RETURN), "Esc / P / Enter"),
        Button("Quit", "quit", (pygame.K_q,), "Q"),
    ], title_colour=(170, 182, 255))


def title_screen(screen_size):
    """The first screen of the game."""
    return TitleScreen(screen_size)
