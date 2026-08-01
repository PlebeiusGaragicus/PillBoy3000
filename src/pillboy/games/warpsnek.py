"""
    Warp Snek — ported from the 2023 PillBoy card
    (`modules/games/warp_snek/warp_snek.py`).

    Snek 1's free-floating physics snake, but with a clock on it: life ticks
    down every frame and the only way to keep going is to keep eating. The
    body's colour lerps from healthy green to a dead, murky green as life
    drains, so you can read your remaining time off the snake itself.

    Food swarms the screen (up to 25 pips at once) and is collected by any part
    of the body brushing it, not just the head — so a long snake sweeps
    up food as it flies.

    Added in the port: a score, and a life bar so the timer is legible at a
    glance. The original's speed-trim buttons (KEY2/KEY3) are kept.
"""
import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.games.palette import lerp
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.gui.screens.screen import ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination


BORDER_WIDTH = 4
SCREEN = 240

STARTING_HEALTH = 120
SNAKE_COLOR_HEALTHY = (90, 255, 50)
SNAKE_COLOR_DEATH = (30, 90, 20)
SNAKE_INIT_SIZE = 8
SNAKE_START = (20, 20)
INIT_SPEED_X = -2
INIT_SPEED_Y = -4
TOP_SPEED = 13

FOOD_SIZE = 6
FOOD_EATING_DISTANCE = 35     # squared distance, as in the original
FOOD_MAX_COUNT = 25
FOOD_LIFE_POWER = 12


class Food:
    def __init__(self):
        self.x = random.randint(BORDER_WIDTH, SCREEN - BORDER_WIDTH - FOOD_SIZE)
        self.y = random.randint(BORDER_WIDTH, SCREEN - BORDER_WIDTH - FOOD_SIZE)
        self.color = (random.randint(100, 255), random.randint(100, 255),
                      random.randint(100, 255))

    def draw(self, draw):
        draw.rectangle((self.x, self.y, self.x + FOOD_SIZE, self.y + FOOD_SIZE),
                       fill=self.color)

    def touched_by(self, body) -> bool:
        for (sx, sy) in body:
            if (sx - self.x) ** 2 + (sy - self.y) ** 2 < FOOD_EATING_DISTANCE ** 2:
                return True
        return False


class WarpSnekGameView(GameView):
    FPS = 30

    CONTROLS = [
        ("Joystick", "WASD", "nudge course"),
        ("Press stick", "Space", "full stop"),
        ("Middle button", "J", "slow down"),
        ("Bottom button", "M", "speed up"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        pts = [(x + w * 0.22, y + h * 0.62), (x + w * 0.40, y + h * 0.34),
               (x + w * 0.60, y + h * 0.64), (x + w * 0.80, y + h * 0.30)]
        for i in range(len(pts) - 1):
            color = lerp(SNAKE_COLOR_DEATH, SNAKE_COLOR_HEALTHY, 1 - i / 3)
            draw.line([pts[i], pts[i + 1]], fill=color, width=9 - i * 2)

    def run(self):
        self.wait_for_release()
        while True:
            result = self._play_round()
            if result is not None:
                return result

    def _play_round(self):
        self.life = STARTING_HEALTH
        self.bigness = SNAKE_INIT_SIZE
        self.speed_x = INIT_SPEED_X
        self.speed_y = INIT_SPEED_Y
        self.score = 0
        self.body = [(SNAKE_START[0] + i * self.speed_x,
                      SNAKE_START[1] + i * self.speed_y) for i in range(10)]
        self.food = [Food()]

        frame_duration = 1.0 / self.FPS
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 14)

        while True:
            frame_start = time.time()

            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()

            self.life -= 1
            if self.life <= 0:
                return self._game_over_screen()

            self._move()

            # Food keeps raining in until the screen is busy
            if len(self.food) < FOOD_MAX_COUNT and random.randint(0, 100) < 90:
                self.food.append(Food())

            for f in self.food[:]:
                if f.touched_by(self.body):
                    self.life += FOOD_LIFE_POWER
                    self.score += 1
                    self.food.remove(f)

            with self.renderer.lock:
                self._render(font)
                self.renderer.show_image()

            elapsed = time.time() - frame_start
            if elapsed < frame_duration:
                time.sleep(frame_duration - elapsed)

    def _move(self):
        hx, hy = self.body[0]
        nx, ny = hx + self.speed_x, hy + self.speed_y

        limit = SCREEN - BORDER_WIDTH - 6
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

        self.body.insert(0, (nx, ny))
        self.body.pop()

    def _render(self, font):
        draw = self.renderer.draw
        draw.rectangle((0, 0, SCREEN, SCREEN), fill="red")
        draw.rectangle((BORDER_WIDTH, BORDER_WIDTH,
                        SCREEN - BORDER_WIDTH, SCREEN - BORDER_WIDTH), fill="black")

        for f in self.food:
            f.draw(draw)

        health_t = max(0.0, min(1.0, self.life / STARTING_HEALTH))
        color = lerp(SNAKE_COLOR_DEATH, SNAKE_COLOR_HEALTHY, health_t)
        half = self.bigness / 2
        for i in range(len(self.body) - 1):
            draw.line([self.body[i][0] + half, self.body[i][1] + half,
                       self.body[i + 1][0] + half, self.body[i + 1][1] + half],
                      fill=color, width=max(1, self.bigness - i))

        # Life bar (added in the port; the original only hinted at it via colour)
        bar_w = int((SCREEN - 2 * BORDER_WIDTH - 60) * health_t)
        draw.rectangle((BORDER_WIDTH + 30, 8, BORDER_WIDTH + 30 + bar_w, 13), fill=color)
        draw.text((8, 6), str(self.score), font=font, fill="white", anchor="lt")

    def _read_input(self):
        K = HardwareButtonsConstants

        if self.buttons.check_for_low(K.KEY_PRESS):
            self.speed_x = 0
            self.speed_y = 0

        if self.buttons.check_for_low(K.KEY2):
            self._trim(-1)
        if self.buttons.check_for_low(K.KEY3):
            self._trim(1)

        if self.buttons.check_for_low(K.KEY_DOWN):
            self._nudge(y_delta=1)
        elif self.buttons.check_for_low(K.KEY_UP):
            self._nudge(y_delta=-1)

        if self.buttons.check_for_low(K.KEY_LEFT):
            self._nudge(x_delta=-1)
        elif self.buttons.check_for_low(K.KEY_RIGHT):
            self._nudge(x_delta=1)

    def _trim(self, delta):
        """Bleed speed off both axes, but never all the way to a dead stop."""
        if abs(self.speed_x) > 1:
            self.speed_x -= delta if self.speed_x > 0 else -delta
        if abs(self.speed_y) > 1:
            self.speed_y -= delta if self.speed_y > 0 else -delta

    def _nudge(self, x_delta: int = None, y_delta: int = None):
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

    def _game_over_screen(self):
        self.wait_for_release()
        AGAIN = ButtonOption("Play again")
        QUIT = ButtonOption("Quit")
        button_data = [AGAIN, QUIT]
        selected = self.run_screen(
            LargeIconStatusScreen,
            title=_("Faded"),
            status_headline=_("Score: {}").format(self.score),
            text=_("The snek ran out of life."),
            button_data=button_data,
            show_back_button=False,
        )
        if button_data[selected] == AGAIN:
            self.wait_for_release()
            return None
        return Destination(BackStackView)
