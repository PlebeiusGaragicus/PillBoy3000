"""
    Shared game colours and helpers, carried over from the 2023 PillBoy card
    (`modules/games/color.py`). Handy for keeping the ported games looking the
    way they originally did.
"""
import os
import pathlib

from PIL import Image


SNEK_GREEN = (90, 255, 50)
SNEK_DEAD = (30, 90, 20)
BRIGHT_GREEN = (50, 255, 0)
GREEN_1 = (40, 230, 0)
GREEN_2 = (20, 210, 0)
LIGHT_GREEN = (20, 200, 0)
DARK_GREEN = (0, 100, 0)
DARK_BROWN = (101, 67, 33)
BRIGHT_GOLD = (255, 215, 0)
LIGHT_GOLD = (255, 236, 139)
DARK_RED = (139, 0, 0)
RED = (200, 20, 20)
LIGHT_RED = (255, 0, 0)
DEEP_PINK = (255, 20, 147)
BRIGHT_PINK = (255, 192, 203)
DARK_DEEP_PINK = (191, 0, 119)
CRIMSON = (220, 20, 60)
DEEP_GREY = (20, 20, 20)
DARK_GREY = (105, 105, 105)
BITCOIN_ORANGE = "#ff9416"


def lerp(color1, color2, t):
    """Linearly interpolate between two RGB colours (t: 0.0 = color1, 1.0 = color2)."""
    t = max(0.0, min(1.0, t))
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t),
    )


def load_sprite(filename: str) -> Image.Image:
    """
        Load a game sprite from resources/img/games, preserving transparency.

        (`gui.components.load_image` converts to RGB, which would turn every
        sprite's transparent background into a black box.)
    """
    path = os.path.join(
        pathlib.Path(__file__).parent.resolve().parent.resolve(),
        "resources", "img", "games", filename)
    return Image.open(path).convert("RGBA")
