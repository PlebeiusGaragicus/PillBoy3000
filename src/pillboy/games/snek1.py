"""
    Snek 1 — ported from the 2023 PillBoy card (`modules/games/snek/snek.py`).

    Not a grid snake at all: the snake is a free-floating body with a velocity.
    The joystick nudges that velocity a step at a time, the head bounces off a
    red border, and the body trails behind as a tapering line. Food is picked
    up by proximity rather than by landing exactly on it.

    Endless by design — the original had no lose condition, so this is a toy
    you leave running rather than a game you can fail. Kept that way on
    purpose; the pause combo is how you leave.

    Added in the port: a score (the original counted nothing) and the food
    respawn no longer double-spawns.
"""
import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.games.palette import BRIGHT_GREEN, lerp
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.hardware.buttons import HardwareButtonsConstants


BORDER_WIDTH = 4
SCREEN = 240
FOOD_SIZE = 6
# The original compares a SQUARED distance against this value, so the real
# pickup radius is sqrt(40) ~= 6.3px -- just about touching. Do not square it
# again when comparing (that mistake makes the radius 40px and food leaps
# into the snake from across the screen).
FOOD_TOLERANCE_SQ = 40
SNAKE_INIT_SIZE = 9
SNAKE_START = (20, 20)
INIT_SPEED_X = -2
INIT_SPEED_Y = -4
TOP_SPEED = 5

FOOD_COLOR = (255, 99, 99)
SNAKE_COLOR = BRIGHT_GREEN


class SnekOneGameView(GameView):
    FPS = 30

    CONTROLS = [
        ("Joystick", "WASD", "nudge course"),
        ("Press stick", "Space", "full stop"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        pts = [(x + w * 0.25, y + h * 0.65), (x + w * 0.40, y + h * 0.35),
               (x + w * 0.58, y + h * 0.62), (x + w * 0.75, y + h * 0.32)]
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=SNAKE_COLOR, width=9 - i * 2)
        draw.rectangle((x + w * 0.78, y + h * 0.28, x + w * 0.78 + 6, y + h * 0.28 + 6),
                       fill=FOOD_COLOR)

    def run(self):
        self.wait_for_release()

        self.bigness = SNAKE_INIT_SIZE
        self.speed_x = INIT_SPEED_X
        self.speed_y = INIT_SPEED_Y
        self.score = 0
        self.snake = [(SNAKE_START[0] + i * self.speed_x,
                       SNAKE_START[1] + i * self.speed_y) for i in range(10)]
        self.food = self._new_food()

        frame_duration = 1.0 / self.FPS
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 14)

        while True:
            frame_start = time.time()

            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()
            self._update()

            with self.renderer.lock:
                draw = self.renderer.draw
                # Border: a red frame with a black interior, as in the original
                draw.rectangle((0, 0, SCREEN, SCREEN), fill="red")
                draw.rectangle((BORDER_WIDTH, BORDER_WIDTH,
                                SCREEN - BORDER_WIDTH, SCREEN - BORDER_WIDTH), fill="black")

                fx, fy = self.food
                draw.rectangle((fx, fy, fx + FOOD_SIZE, fy + FOOD_SIZE), fill=FOOD_COLOR)

                # Body as a tapering polyline (width shrinks toward the tail)
                half = self.bigness / 2
                for i in range(len(self.snake) - 1):
                    width = max(1, self.bigness - i)
                    draw.line([self.snake[i][0] + half, self.snake[i][1] + half,
                               self.snake[i + 1][0] + half, self.snake[i + 1][1] + half],
                              fill=SNAKE_COLOR, width=width)

                draw.text((8, 8), str(self.score), font=font, fill="white", anchor="lt")
                self.renderer.show_image()

            elapsed = time.time() - frame_start
            if elapsed < frame_duration:
                time.sleep(frame_duration - elapsed)

    def _new_food(self):
        return (random.randint(BORDER_WIDTH, SCREEN - BORDER_WIDTH - FOOD_SIZE),
                random.randint(BORDER_WIDTH, SCREEN - BORDER_WIDTH - FOOD_SIZE))

    def _update(self):
        hx, hy = self.snake[0]
        nx, ny = hx + self.speed_x, hy + self.speed_y

        # Bounce off the border
        limit = SCREEN - BORDER_WIDTH - self.bigness
        if nx < BORDER_WIDTH:
            self.speed_x = -self.speed_x
            nx = BORDER_WIDTH
        elif nx > limit:
            self.speed_x = -self.speed_x
            nx = limit
        if ny < BORDER_WIDTH:
            self.speed_y = -self.speed_y
            ny = BORDER_WIDTH
        elif ny > limit:
            self.speed_y = -self.speed_y
            ny = limit

        self.snake.insert(0, (nx, ny))
        self.snake.pop()

        # Proximity pickup
        fx, fy = self.food
        if (nx - fx) ** 2 + (ny - fy) ** 2 < FOOD_TOLERANCE_SQ:
            self.score += 1
            self.food = self._new_food()

    def _read_input(self):
        """Joystick nudges velocity; centre press brings the snake to a halt."""
        K = HardwareButtonsConstants

        if self.buttons.check_for_low(K.KEY_PRESS):
            self.speed_x = 0
            self.speed_y = 0

        if self.buttons.check_for_low(K.KEY_DOWN):
            self._nudge(y_delta=1)
        elif self.buttons.check_for_low(K.KEY_UP):
            self._nudge(y_delta=-1)

        if self.buttons.check_for_low(K.KEY_LEFT):
            self._nudge(x_delta=-1)
        elif self.buttons.check_for_low(K.KEY_RIGHT):
            self._nudge(x_delta=1)

    def _nudge(self, x_delta: int = None, y_delta: int = None):
        """
            Speeding up on one axis past TOP_SPEED bleeds speed off the other
            axis instead — the original's way of keeping the snake controllable.
        """
        if x_delta is not None:
            if abs(self.speed_x) > TOP_SPEED:
                self.speed_x = TOP_SPEED if self.speed_x > 0 else -TOP_SPEED
                if self.speed_y:
                    self.speed_y -= 1 if self.speed_y > 0 else -1
            else:
                self.speed_x += x_delta

        if y_delta is not None:
            if abs(self.speed_y) > TOP_SPEED:
                self.speed_y = TOP_SPEED if self.speed_y > 0 else -TOP_SPEED
                if self.speed_x:
                    self.speed_x -= 1 if self.speed_x > 0 else -1
            else:
                self.speed_y += y_delta
