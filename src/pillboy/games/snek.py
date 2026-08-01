"""
    Snek — a port of an older pygame "snek" prototype, keeping its ergonomics:

      * the playfield wraps: run off an edge and you reappear on the opposite side
      * constant speed — it never accelerates, no matter how long you get
      * the only way to die is to bite yourself

    Which makes it a much more forgiving, meditative game than `snake.py`
    (walls kill there, and it speeds up as you eat). To keep the two feeling
    distinct they also differ in how you steer and how they look:

      snake.py : absolute steering — the joystick points the snake
      snek.py  : rotation steering — buttons turn you left/right, Asteroids-style

    Fixed from the original prototype: food could spawn underneath the snake,
    there was no score, and screen dimensions leaked in through globals.
"""
import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.gui.screens.screen import ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination


# Clockwise, so a "turn right" is +1 and a "turn left" is -1 around this ring
DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]   # up, right, down, left

BG_COLOR = "#06120a"
DOT_COLOR = "#12301c"
EDGE_COLOR = "#1d4a2c"
HEAD_COLOR = "#b6ff7a"
BODY_BRIGHT = (60, 220, 90)
BODY_DARK = (18, 90, 40)
FOOD_COLOR = "#ff4d6d"
FOOD_GLOW = "#7a1f2e"
EYE_COLOR = "#06120a"


class SnekGameView(GameView):
    COLS = 24
    ROWS = 24
    CELL = 10                 # 24 * 10 = 240, exactly the screen
    STEP = 0.11               # constant, never changes (the original's FPS 10)

    CONTROLS = [
        ("Top button", "U", "turn left"),
        ("Bottom button", "M", "turn right"),
        ("Press stick", "Space", "turn right"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        cell = 12
        cx = x + (w - 5 * cell) // 2
        cy = y + h // 2 - cell // 2
        for i in range(4):
            t = i / 3
            color = tuple(int(BODY_DARK[j] + (BODY_BRIGHT[j] - BODY_DARK[j]) * t)
                          for j in range(3))
            draw.ellipse((cx + i * cell, cy, cx + i * cell + cell - 1, cy + cell - 1),
                         fill=color)
        draw.ellipse((cx + 4 * cell + 2, cy + 2,
                      cx + 4 * cell + cell - 2, cy + cell - 2), fill=FOOD_COLOR)

    # ------------------------------------------------------------------ entry
    def run(self):
        self.wait_for_release()
        while True:
            result = self._play_round()
            if result is not None:
                return result

    # ------------------------------------------------------------------ round
    def _play_round(self):
        mid_r = self.ROWS // 2
        self.snake = [(3, mid_r), (4, mid_r), (5, mid_r)]   # tail .. head
        self.heading = 1                                     # index into DIRECTIONS
        self.score = 0
        self.food = self._place_food()
        self.frame = 0

        dest = self._wait_to_start()
        if dest:
            return dest

        last_step = time.time()
        while True:
            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()
            self.frame += 1

            now = time.time()
            if now - last_step >= self.STEP:
                last_step = now
                if not self._advance():
                    return self._game_over_screen()

            with self.renderer.lock:
                self._render()
                self.renderer.show_image()

            time.sleep(0.02)

    def _advance(self) -> bool:
        """Move one cell. Returns False if the snake bit itself."""
        dx, dy = DIRECTIONS[self.heading]
        hx, hy = self.snake[-1]
        # The wrap: this is the whole personality of the original game
        new_head = ((hx + dx) % self.COLS, (hy + dy) % self.ROWS)

        # The tail cell is about to be vacated, so it's not a collision
        body = self.snake[1:] if new_head != self.food else self.snake
        if new_head in body:
            return False

        self.snake.append(new_head)
        if new_head == self.food:
            self.score += 1
            self.food = self._place_food()
        else:
            self.snake.pop(0)
        return True

    def _place_food(self):
        free = [(c, r) for c in range(self.COLS) for r in range(self.ROWS)
                if (c, r) not in self.snake]
        return random.choice(free) if free else None

    # ------------------------------------------------------------------ input
    def _read_input(self):
        """Rotation steering: no absolute direction, just turn left or right."""
        K = HardwareButtonsConstants
        if self._tap("left", K.KEY1):
            self.heading = (self.heading - 1) % 4
        if self._tap("right", K.KEY3) or self._tap("right2", K.KEY_PRESS):
            self.heading = (self.heading + 1) % 4

    def _tap(self, name, key) -> bool:
        """Edge-triggered: one turn per press, holding does not spin you."""
        if not hasattr(self, "_held"):
            self._held = set()
        if self.buttons.check_for_low(key):
            if name in self._held:
                return False
            self._held.add(name)
            return True
        self._held.discard(name)
        return False

    def _wait_to_start(self):
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        while True:
            dest = self.check_pause_menu()
            if dest:
                return dest
            if self.buttons.check_for_low(keys=[
                    HardwareButtonsConstants.KEY1,
                    HardwareButtonsConstants.KEY3,
                    HardwareButtonsConstants.KEY_PRESS]):
                while self.buttons.has_any_input():
                    time.sleep(0.01)
                return None

            self.frame += 1
            with self.renderer.lock:
                self._render()
                if (self.frame // 12) % 2 == 0:
                    self.renderer.draw.text(
                        (self.canvas_width // 2, self.canvas_height // 2 + 40),
                        _("Push to start"), font=font, fill="white", anchor="mm",
                        stroke_width=3, stroke_fill=BG_COLOR)
                self.renderer.show_image()
            time.sleep(0.03)

    # ---------------------------------------------------------------- render
    def _render(self):
        draw = self.renderer.draw
        draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill=BG_COLOR)

        # Faint dot grid, plus a dashed edge as a reminder that the field wraps
        for r in range(self.ROWS):
            for c in range(self.COLS):
                if (r + c) % 2 == 0:
                    draw.point((c * self.CELL + self.CELL // 2,
                                r * self.CELL + self.CELL // 2), fill=DOT_COLOR)
        for i in range(0, self.canvas_width, 8):
            draw.line((i, 0, i + 4, 0), fill=EDGE_COLOR)
            draw.line((i, self.canvas_height - 1, i + 4, self.canvas_height - 1), fill=EDGE_COLOR)
            draw.line((0, i, 0, i + 4), fill=EDGE_COLOR)
            draw.line((self.canvas_width - 1, i, self.canvas_width - 1, i + 4), fill=EDGE_COLOR)

        if self.food:
            self._draw_food(draw, *self.food)

        # Body: rounded segments fading from tail to head
        n = len(self.snake)
        for i, (c, r) in enumerate(self.snake):
            is_head = (i == n - 1)
            x0 = c * self.CELL
            y0 = r * self.CELL
            if is_head:
                draw.ellipse((x0, y0, x0 + self.CELL - 1, y0 + self.CELL - 1), fill=HEAD_COLOR)
                self._draw_eyes(draw, x0, y0)
            else:
                t = i / max(1, n - 1)
                color = tuple(int(BODY_DARK[j] + (BODY_BRIGHT[j] - BODY_DARK[j]) * t)
                              for j in range(3))
                inset = 1 if t > 0.35 else 2
                draw.ellipse((x0 + inset, y0 + inset,
                              x0 + self.CELL - 1 - inset, y0 + self.CELL - 1 - inset),
                             fill=color)

        font = Fonts.get_font(GUIConstants.get_body_font_name(), 14)
        draw.text((5, 5), str(self.score), font=font, fill="white",
                  anchor="lt", stroke_width=3, stroke_fill=BG_COLOR)

    def _draw_eyes(self, draw, x0, y0):
        dx, dy = DIRECTIONS[self.heading]
        cx = x0 + self.CELL / 2
        cy = y0 + self.CELL / 2
        # Offset the pair perpendicular to travel, pushed toward the front
        px, py = -dy, dx
        for side in (-1, 1):
            ex = cx + dx * 2 + px * side * 2.2
            ey = cy + dy * 2 + py * side * 2.2
            draw.ellipse((ex - 1.2, ey - 1.2, ex + 1.2, ey + 1.2), fill=EYE_COLOR)

    def _draw_food(self, draw, c, r):
        cx = c * self.CELL + self.CELL / 2
        cy = r * self.CELL + self.CELL / 2
        pulse = 1.0 + 0.25 * ((self.frame // 6) % 2)
        rr = (self.CELL / 2 - 1) * pulse
        draw.ellipse((cx - rr - 1, cy - rr - 1, cx + rr + 1, cy + rr + 1), fill=FOOD_GLOW)
        draw.ellipse((cx - rr + 1, cy - rr + 1, cx + rr - 1, cy + rr - 1), fill=FOOD_COLOR)

    # ------------------------------------------------------------------- end
    def _game_over_screen(self):
        self.wait_for_release()
        AGAIN = ButtonOption("Play again")
        QUIT = ButtonOption("Quit")
        button_data = [AGAIN, QUIT]
        selected = self.run_screen(
            LargeIconStatusScreen,
            title=_("Ouch"),
            status_headline=_("Score: {}").format(self.score),
            text=_("You bit yourself."),
            button_data=button_data,
            show_back_button=False,
        )
        if button_data[selected] == AGAIN:
            self.wait_for_release()
            return None
        return Destination(BackStackView)
