"""Screen size and sharpness on high-resolution displays.

The game is designed for a 960x640 window. On a screen where Windows
scales everything up (e.g. 200% on a laptop), Windows would normally stretch
that small window, making everything blurry and blocky. Instead, the game
tells Windows it handles scaling itself, opens a bigger window, and every
part of the game draws at that bigger size, so edges and text stay sharp.
"""

import sys

BASE_SIZE = (960, 640)


def scale_of(size):
    """Return how much bigger than BASE_SIZE a window size is (1.0 = design size)."""
    return size[0] / BASE_SIZE[0]


def setup_window_scale():
    """Make the game DPI-aware on Windows and return the scale to draw at.

    Returns 1.0 on other systems, or if anything goes wrong, so the game
    always still runs.
    """
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()      # older Windows
        scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
        # Never make the window bigger than about 90% of the real screen.
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        fit = min(screen_w * 0.9 / BASE_SIZE[0], screen_h * 0.9 / BASE_SIZE[1])
        return max(1.0, min(scale, fit))
    except (AttributeError, OSError):
        return 1.0


def window_size(scale):
    """The window size in pixels for a given scale."""
    return (round(BASE_SIZE[0] * scale), round(BASE_SIZE[1] * scale))
