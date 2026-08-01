"""
    Grubs — ported from the 2023 PillBoy card (`modules/games/grubs/grubs.py`).

    The simplest of the card's snakes: white blocks on black, a red fruit,
    absolute joystick steering, 6px steps. The original was a sketch — it had
    no bounds check at all, so steering off an edge sent the grub away forever
    with no way back. The port wraps at the edges instead, which is the
    smallest change that makes it playable while keeping its "no way to lose"
    character.

    Also added in the port: a score.
"""
import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.hardware.buttons import HardwareButtonsConstants


STEP = 6
SCREEN = 240
CELLS = SCREEN // STEP        # 40


class GrubsGameView(GameView):
    MOVE_INTERVAL = 0.07

    CONTROLS = [
        ("Joystick", "WASD", "steer"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        cx = x + w // 2 - 30
        cy = y + h // 2 - 6
        for i in range(5):
            draw.rectangle((cx + i * 13, cy, cx + i * 13 + 11, cy + 11), fill="white")
        draw.ellipse((cx + 5 * 13 + 4, cy, cx + 5 * 13 + 15, cy + 11), fill="red")

    def run(self):
        self.wait_for_release()

        mid = (CELLS // 2) * STEP
        self.grub = [(mid - 2 * STEP, mid), (mid - STEP, mid), (mid, mid)]
        self.direction = "RIGHT"
        self.fruit = self._new_fruit()
        self.score = 0

        font = Fonts.get_font(GUIConstants.get_body_font_name(), 14)
        last_move = time.time()

        while True:
            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()

            if time.time() - last_move >= self.MOVE_INTERVAL:
                last_move = time.time()
                self._move()

            with self.renderer.lock:
                draw = self.renderer.draw
                draw.rectangle((0, 0, SCREEN, SCREEN), fill="black")
                for (gx, gy) in self.grub:
                    draw.rectangle((gx, gy, gx + STEP, gy + STEP), fill="white")
                fx, fy = self.fruit
                draw.ellipse((fx, fy, fx + STEP, fy + STEP), fill="red")
                draw.text((6, 6), str(self.score), font=font, fill="#888888", anchor="lt")
                self.renderer.show_image()

            time.sleep(0.01)

    def _new_fruit(self):
        while True:
            spot = (random.randrange(CELLS) * STEP, random.randrange(CELLS) * STEP)
            if spot not in self.grub:
                return spot

    def _move(self):
        hx, hy = self.grub[-1]
        dx, dy = {"RIGHT": (STEP, 0), "LEFT": (-STEP, 0),
                  "UP": (0, -STEP), "DOWN": (0, STEP)}[self.direction]
        # Wrap instead of wandering off the screen forever
        new_head = ((hx + dx) % SCREEN, (hy + dy) % SCREEN)

        self.grub.append(new_head)
        if new_head == self.fruit:
            self.score += 1
            self.fruit = self._new_fruit()
        else:
            self.grub.pop(0)

    def _read_input(self):
        K = HardwareButtonsConstants
        if self.buttons.check_for_low(K.KEY_DOWN):
            self.direction = "DOWN"
        elif self.buttons.check_for_low(K.KEY_UP):
            self.direction = "UP"
        elif self.buttons.check_for_low(K.KEY_LEFT):
            self.direction = "LEFT"
        elif self.buttons.check_for_low(K.KEY_RIGHT):
            self.direction = "RIGHT"
