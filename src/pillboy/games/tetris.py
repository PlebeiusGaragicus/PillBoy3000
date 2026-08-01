import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.gui.screens.screen import ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination


# Tetromino shapes as (col, row) cells in their spawn orientation, inside a
# bounding box (box_size x box_size) that they rotate within.
PIECES = {
    "I": {"cells": [(0, 1), (1, 1), (2, 1), (3, 1)], "box": 4, "color": "#00d8d8"},
    "O": {"cells": [(1, 0), (2, 0), (1, 1), (2, 1)], "box": 4, "color": "#d8d800"},
    "T": {"cells": [(1, 0), (0, 1), (1, 1), (2, 1)], "box": 3, "color": "#b000d8"},
    "S": {"cells": [(1, 0), (2, 0), (0, 1), (1, 1)], "box": 3, "color": "#00d800"},
    "Z": {"cells": [(0, 0), (1, 0), (1, 1), (2, 1)], "box": 3, "color": "#d80000"},
    "J": {"cells": [(0, 0), (0, 1), (1, 1), (2, 1)], "box": 3, "color": "#0000d8"},
    "L": {"cells": [(2, 0), (0, 1), (1, 1), (2, 1)], "box": 3, "color": "#d88000"},
}

LINE_SCORES = {1: 40, 2: 100, 3: 300, 4: 1200}


def rotate_cells(cells, box, times):
    """Rotate cells clockwise `times` times within their box."""
    out = list(cells)
    for _i in range(times % 4):
        out = [(box - 1 - r, c) for (c, r) in out]
    return out


class TetrisGameView(GameView):
    """
        Classic falling-blocks game.

        Controls: left/right move, up rotate CW, down soft drop,
        KEY1 rotate CW, KEY2 rotate CCW, KEY3 hard drop.
        All three side buttons together: pause menu (from GameView).
    """
    FPS = 30
    COLS = 10
    ROWS = 20

    CONTROLS = [
        ("Joystick left/right", "A/D", "move"),
        ("Joystick up", "W", "rotate"),
        ("Joystick down", "S", "soft drop"),
        ("Top button", "U", "rotate"),
        ("Middle button", "J", "rotate back"),
        ("Bottom button", "M", "hard drop"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        # A little T + I piece vignette
        cell = 14
        cx = x + (w - 5 * cell) // 2
        cy = y + (h - 3 * cell) // 2
        for (c, r, color) in [
            (1, 0, PIECES["T"]["color"]), (0, 1, PIECES["T"]["color"]),
            (1, 1, PIECES["T"]["color"]), (2, 1, PIECES["T"]["color"]),
            (4, 0, PIECES["I"]["color"]), (4, 1, PIECES["I"]["color"]),
            (4, 2, PIECES["I"]["color"]),
        ]:
            px = cx + c * cell
            py = cy + r * cell
            draw.rectangle((px, py, px + cell - 2, py + cell - 2),
                           fill=color, outline="black")

    # Input timing (seconds)
    SHIFT_DELAY = 0.17    # hold delay before left/right auto-repeat
    SHIFT_REPEAT = 0.05
    SOFT_DROP_REPEAT = 0.04

    GRID_COLOR = "#222222"
    FIELD_BG = "#000000"

    def run(self):
        self.wait_for_release()

        # Layout: field fills screen height; panel on the right
        self.cell = self.canvas_height // self.ROWS                  # 12px at 240
        self.field_w = self.cell * self.COLS                         # 120
        self.field_x = 8
        self.field_y = (self.canvas_height - self.cell * self.ROWS) // 2
        self.panel_x = self.field_x + self.field_w + 10

        while True:
            result = self._play_round()
            if result is not None:
                return result


    # ------------------------------------------------------------------ round
    def _play_round(self):
        """One full game. Returns a Destination to exit, or None to play again."""
        self.board = [[None] * self.COLS for _ in range(self.ROWS)]
        self.score = 0
        self.lines = 0
        self.level = 1
        self.bag = []
        self.next_name = self._draw_from_bag()
        self._spawn_piece()

        # Per-key input state: name -> {held_since, last_repeat}
        self._key_state = {}

        frame_duration = 1.0 / self.FPS
        last_gravity = time.time()

        while True:
            frame_start = time.time()

            dest = self.check_pause_menu()
            if dest:
                return dest

            # ---- input
            game_over = False
            if self._pressed("left", HardwareButtonsConstants.KEY_LEFT,
                             self.SHIFT_DELAY, self.SHIFT_REPEAT):
                self._try_move(-1, 0)
            if self._pressed("right", HardwareButtonsConstants.KEY_RIGHT,
                             self.SHIFT_DELAY, self.SHIFT_REPEAT):
                self._try_move(1, 0)
            if self._pressed("rot_cw", HardwareButtonsConstants.KEY_UP):
                self._try_rotate(1)
            if self._pressed("rot_cw2", HardwareButtonsConstants.KEY1):
                self._try_rotate(1)
            if self._pressed("rot_ccw", HardwareButtonsConstants.KEY2):
                self._try_rotate(-1)
            if self._pressed("soft", HardwareButtonsConstants.KEY_DOWN,
                             0.0, self.SOFT_DROP_REPEAT):
                if self._try_move(0, 1):
                    self.score += 1
                    last_gravity = time.time()
                else:
                    game_over = not self._lock_piece()
            if self._pressed("hard", HardwareButtonsConstants.KEY3):
                while self._try_move(0, 1):
                    self.score += 2
                game_over = not self._lock_piece()
                last_gravity = time.time()

            # ---- gravity
            if not game_over and time.time() - last_gravity >= self._gravity_delay():
                last_gravity = time.time()
                if not self._try_move(0, 1):
                    game_over = not self._lock_piece()

            if game_over:
                return self._game_over_screen()

            # ---- render
            with self.renderer.lock:
                self._render()
                self.renderer.show_image()

            elapsed = time.time() - frame_start
            if elapsed < frame_duration:
                time.sleep(frame_duration - elapsed)


    # ------------------------------------------------------------------ pieces
    def _draw_from_bag(self):
        if not self.bag:
            self.bag = list(PIECES.keys())
            random.shuffle(self.bag)
        return self.bag.pop()

    def _spawn_piece(self):
        self.piece_name = self.next_name
        self.next_name = self._draw_from_bag()
        self.rotation = 0
        piece = PIECES[self.piece_name]
        self.px = (self.COLS - piece["box"]) // 2
        self.py = -1  # spawn partly above the visible field

    def _piece_cells(self, px=None, py=None, rotation=None):
        piece = PIECES[self.piece_name]
        px = self.px if px is None else px
        py = self.py if py is None else py
        rotation = self.rotation if rotation is None else rotation
        return [(px + c, py + r)
                for (c, r) in rotate_cells(piece["cells"], piece["box"], rotation)]

    def _fits(self, cells):
        for (c, r) in cells:
            if c < 0 or c >= self.COLS or r >= self.ROWS:
                return False
            if r >= 0 and self.board[r][c] is not None:
                return False
        return True

    def _try_move(self, dx, dy) -> bool:
        if self._fits(self._piece_cells(px=self.px + dx, py=self.py + dy)):
            self.px += dx
            self.py += dy
            return True
        return False

    def _try_rotate(self, direction):
        new_rotation = (self.rotation + direction) % 4
        # simple wall kicks: try in place, then shifted 1 left/right
        for kick in (0, -1, 1):
            if self._fits(self._piece_cells(px=self.px + kick, rotation=new_rotation)):
                self.px += kick
                self.rotation = new_rotation
                return

    def _lock_piece(self) -> bool:
        """Lock the current piece, clear lines, spawn next. False = game over."""
        for (c, r) in self._piece_cells():
            if r < 0:
                return False  # locked above the field: game over
            self.board[r][c] = PIECES[self.piece_name]["color"]

        full_rows = [r for r in range(self.ROWS) if all(self.board[r])]
        if full_rows:
            for r in full_rows:
                del self.board[r]
                self.board.insert(0, [None] * self.COLS)
            self.lines += len(full_rows)
            self.score += LINE_SCORES[len(full_rows)] * self.level
            self.level = 1 + self.lines // 10

        self._spawn_piece()
        return self._fits(self._piece_cells())

    def _gravity_delay(self) -> float:
        # Level 1: 0.8s per row, ~15% faster per level, floor at 0.08s
        return max(0.08, 0.8 * (0.85 ** (self.level - 1)))


    # ------------------------------------------------------------------ input
    def _pressed(self, name, key, repeat_delay=None, repeat_rate=None) -> bool:
        """
            Edge-triggered press detection with optional hold-to-repeat.
            Returns True when the action should fire this frame.
        """
        now = time.time()
        state = self._key_state.get(name)
        if self.buttons.check_for_low(key):
            if state is None:
                self._key_state[name] = {"held_since": now, "last_repeat": now}
                return True
            if repeat_delay is None:
                return False  # single-shot key (rotate, hard drop)
            if now - state["held_since"] >= repeat_delay and \
                    now - state["last_repeat"] >= (repeat_rate or 0):
                state["last_repeat"] = now
                return True
            return False
        else:
            self._key_state.pop(name, None)
            return False


    # ------------------------------------------------------------------ render
    def _cell_rect(self, c, r):
        x = self.field_x + c * self.cell
        y = self.field_y + r * self.cell
        return (x, y, x + self.cell - 1, y + self.cell - 1)

    def _render(self):
        draw = self.renderer.draw
        draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill="black")

        # Field border + background
        draw.rectangle(
            (self.field_x - 2, self.field_y - 2,
             self.field_x + self.field_w + 1, self.field_y + self.cell * self.ROWS + 1),
            outline="#555555", fill=self.FIELD_BG)

        # Locked cells
        for r in range(self.ROWS):
            for c in range(self.COLS):
                color = self.board[r][c]
                if color:
                    draw.rectangle(self._cell_rect(c, r), fill=color, outline="black")

        # Current piece
        color = PIECES[self.piece_name]["color"]
        for (c, r) in self._piece_cells():
            if r >= 0:
                draw.rectangle(self._cell_rect(c, r), fill=color, outline="black")

        # Side panel: next piece preview + score
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        draw.text((self.panel_x, 8), _("Next"), font=font, fill="#aaaaaa")
        preview = PIECES[self.next_name]
        pc = 8  # preview cell size
        for (c, r) in preview["cells"]:
            x = self.panel_x + c * pc
            y = 28 + r * pc
            draw.rectangle((x, y, x + pc - 1, y + pc - 1),
                           fill=preview["color"], outline="black")

        draw.text((self.panel_x, 78), _("Score"), font=font, fill="#aaaaaa")
        draw.text((self.panel_x, 96), str(self.score), font=font, fill="white")
        draw.text((self.panel_x, 126), _("Lines"), font=font, fill="#aaaaaa")
        draw.text((self.panel_x, 144), str(self.lines), font=font, fill="white")
        draw.text((self.panel_x, 174), _("Level"), font=font, fill="#aaaaaa")
        draw.text((self.panel_x, 192), str(self.level), font=font, fill="white")


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
            text=_("{} lines, level {}").format(self.lines, self.level),
            button_data=button_data,
            show_back_button=False,
        )

        if button_data[selected_menu_num] == PLAY_AGAIN:
            self.wait_for_release()
            return None

        return Destination(BackStackView)
