import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.gui.screens.screen import ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination


UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

SNAKE_HEAD_COLOR = "#8cff5a"
SNAKE_COLOR = "#00c832"
FOOD_COLOR = "#ff3232"
WALL_COLOR = "#555555"


class SnakeGameView(GameView):
    """
        Classic snake. Eat the food, grow, don't bite yourself or the walls.
        Speed increases as you grow.
    """
    COLS = 20
    ROWS = 18          # leaves room for the score bar at the top
    CELL = 12          # 20*12 = 240 wide, 18*12 = 216 tall
    HEADER_H = 24

    START_DELAY = 0.18   # seconds per step
    MIN_DELAY = 0.06
    SPEEDUP_PER_FOOD = 0.004

    CONTROLS = [
        ("Joystick", "WASD", "turn"),
        ("Top button", "U", "turn left"),
        ("Bottom button", "M", "turn right"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        cell = 12
        cx = x + (w - 5 * cell) // 2
        cy = y + h // 2 - cell // 2
        for i in range(4):
            color = SNAKE_HEAD_COLOR if i == 3 else SNAKE_COLOR
            draw.rectangle((cx + i * cell, cy, cx + i * cell + cell - 2, cy + cell - 2),
                           fill=color)
        draw.ellipse((cx + 4 * cell + 2, cy + 2,
                      cx + 4 * cell + cell - 2, cy + cell - 2), fill=FOOD_COLOR)

    def run(self):
        self.wait_for_release()
        while True:
            result = self._play_round()
            if result is not None:
                return result


    # ------------------------------------------------------------------ round
    def _play_round(self):
        mid_c, mid_r = self.COLS // 2, self.ROWS // 2
        self.snake = [(mid_c - 2, mid_r), (mid_c - 1, mid_r), (mid_c, mid_r)]
        self.direction = RIGHT
        self.pending_direction = RIGHT
        self.score = 0
        self.food = self._place_food()
        delay = self.START_DELAY

        # Don't start moving until the player is actually looking at the screen:
        # hold the board still until the first steering input.
        dest = self._wait_to_start()
        if dest:
            return dest
        last_step = time.time()

        while True:
            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()

            now = time.time()
            if now - last_step >= delay:
                last_step = now
                self.direction = self.pending_direction
                head_c, head_r = self.snake[-1]
                new_head = (head_c + self.direction[0], head_r + self.direction[1])

                # Wall or self collision ends the round
                if not (0 <= new_head[0] < self.COLS and 0 <= new_head[1] < self.ROWS) \
                        or new_head in self.snake[1:]:
                    return self._game_over_screen()

                self.snake.append(new_head)
                if new_head == self.food:
                    self.score += 1
                    self.food = self._place_food()
                    delay = max(self.MIN_DELAY, delay - self.SPEEDUP_PER_FOOD)
                else:
                    self.snake.pop(0)

                with self.renderer.lock:
                    self._render()
                    self.renderer.show_image()

            time.sleep(0.005)


    def _wait_to_start(self):
        """
            Show the starting board with a prompt and hold until the player
            gives a direction. Returns a Destination if they paused and quit.
        """
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        blink = True
        last_blink = time.time()

        while True:
            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()
            if self.pending_direction != self.direction or \
                    self.buttons.check_for_low(HardwareButtonsConstants.KEY_RIGHT):
                return None

            if time.time() - last_blink > 0.5:
                blink = not blink
                last_blink = time.time()

            with self.renderer.lock:
                self._render()
                if blink:
                    y = self.HEADER_H + (self.ROWS * self.CELL) // 2
                    self.renderer.draw.text(
                        (self.canvas_width // 2, y), _("Push to start"),
                        font=font, fill="white", anchor="mm",
                        stroke_width=3, stroke_fill="black")
                self.renderer.show_image()

            time.sleep(0.03)


    # ------------------------------------------------------------------ input
    def _read_input(self):
        """
            Absolute steering with the joystick, plus relative turns on the side
            buttons. Reversing directly onto yourself is ignored.
        """
        d = None
        if self.buttons.check_for_low(HardwareButtonsConstants.KEY_UP):
            d = UP
        elif self.buttons.check_for_low(HardwareButtonsConstants.KEY_DOWN):
            d = DOWN
        elif self.buttons.check_for_low(HardwareButtonsConstants.KEY_LEFT):
            d = LEFT
        elif self.buttons.check_for_low(HardwareButtonsConstants.KEY_RIGHT):
            d = RIGHT
        elif self.buttons.check_for_low(HardwareButtonsConstants.KEY1):
            # turn left (counter-clockwise) relative to current heading
            d = (self.direction[1], -self.direction[0])
        elif self.buttons.check_for_low(HardwareButtonsConstants.KEY3):
            # turn right (clockwise)
            d = (-self.direction[1], self.direction[0])

        if d and (d[0] != -self.direction[0] or d[1] != -self.direction[1]):
            self.pending_direction = d


    def _place_food(self):
        free = [(c, r) for c in range(self.COLS) for r in range(self.ROWS)
                if (c, r) not in self.snake]
        return random.choice(free) if free else None


    # ------------------------------------------------------------------ render
    def _cell_rect(self, c, r, inset=1):
        x = c * self.CELL
        y = self.HEADER_H + r * self.CELL
        return (x + inset, y + inset, x + self.CELL - 1 - inset, y + self.CELL - 1 - inset)

    def _render(self):
        draw = self.renderer.draw
        draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill="black")

        font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        draw.text((6, self.HEADER_H // 2), _("Score {}").format(self.score),
                  font=font, fill="white", anchor="lm")
        draw.text((self.canvas_width - 6, self.HEADER_H // 2),
                  _("Len {}").format(len(self.snake)),
                  font=font, fill="#aaaaaa", anchor="rm")

        # Play-field border
        field_bottom = self.HEADER_H + self.ROWS * self.CELL
        draw.rectangle((0, self.HEADER_H - 1, self.canvas_width - 1, field_bottom),
                       outline=WALL_COLOR)

        if self.food:
            draw.ellipse(self._cell_rect(*self.food, inset=1), fill=FOOD_COLOR)

        for i, (c, r) in enumerate(self.snake):
            is_head = (i == len(self.snake) - 1)
            draw.rectangle(self._cell_rect(c, r, inset=0 if is_head else 1),
                           fill=SNAKE_HEAD_COLOR if is_head else SNAKE_COLOR)


    # ------------------------------------------------------------------ end
    def _game_over_screen(self):
        """Returns a Destination to exit, or None to play again."""
        self.wait_for_release()

        PLAY_AGAIN = ButtonOption("Play again")
        QUIT = ButtonOption("Quit")
        button_data = [PLAY_AGAIN, QUIT]
        selected_menu_num = self.run_screen(
            LargeIconStatusScreen,
            title=_("Game Over"),
            status_headline=_("Score: {}").format(self.score),
            text=_("Length {}").format(len(self.snake)),
            button_data=button_data,
            show_back_button=False,
        )

        if button_data[selected_menu_num] == PLAY_AGAIN:
            self.wait_for_release()
            return None

        return Destination(BackStackView)
