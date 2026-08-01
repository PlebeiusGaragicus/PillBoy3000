import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.gui.screens.screen import ButtonListScreen, ButtonOption, LargeIconStatusScreen
from pillboy.gui.screens import RET_CODE__BACK_BUTTON
from pillboy.hardware.buttons import HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination


# Base puzzles, each verified to have exactly one solution. At runtime they're
# passed through a random isomorphic transform (digit relabeling, row/column
# shuffles within bands, band shuffles, transpose) which preserves uniqueness
# while giving ~10^9 variations per base — so puzzles look fresh without
# running an expensive generator on the Pi Zero.
PUZZLES = {
    "easy": [
        "061082090940050068805000007309000400170205680280190005597300820403000006010520300",
        "400217300617800020900560187070008090840650713030100045750006030090720006000430000",
        "080040501103528600005006890450810700010670085037052916000005070500000000378004059",
    ],
    "medium": [
        "204607000690050014300040000050079000980000030100400970720094300001060000000802160",
        "000600200254900076069042000000090020040207060090001030901000700007409600020718000",
        "100069400000000930092034685520300800008005000970648000009501006030200500000000090",
    ],
    "hard": [
        "047020085030400000009500200020009006400006010003000004090705002000002007700000060",
        "000082405000000013000013700040000070090007002630120000004000050000800000010030269",
        "070600003105000900000140000012069300000080004080300600200000437503000010000030000",
    ],
}

GIVEN_COLOR = "#ffffff"
ENTRY_COLOR = GUIConstants.ACCENT_COLOR
CONFLICT_COLOR = "#ff4a4a"
GRID_COLOR = "#3a3f46"
BAND_COLOR = "#8a9099"
CURSOR_COLOR = GUIConstants.ACCENT_COLOR
PEER_COLOR = "#1e2126"


def transform(flat: str) -> list[list[int]]:
    """Return a random isomorphic variant of a base puzzle as a 9x9 int grid."""
    grid = [[int(flat[r * 9 + c]) for c in range(9)] for r in range(9)]

    # Relabel digits 1-9
    mapping = list(range(1, 10))
    random.shuffle(mapping)
    mapping = {d: mapping[d - 1] for d in range(1, 10)}
    grid = [[mapping[v] if v else 0 for v in row] for row in grid]

    # Shuffle rows within each band, then the bands themselves
    def shuffle_bands(g):
        bands = [g[i * 3:(i + 1) * 3] for i in range(3)]
        for band in bands:
            random.shuffle(band)
        random.shuffle(bands)
        return [row for band in bands for row in band]

    grid = shuffle_bands(grid)
    grid = [list(row) for row in zip(*grid)]   # transpose -> columns become rows
    grid = shuffle_bands(grid)
    if random.random() < 0.5:
        grid = [list(row) for row in zip(*grid)]   # keep the transpose sometimes

    return grid


class SudokuGameView(GameView):
    """
        Sudoku with joystick navigation and digit cycling on the side buttons.
    """
    CELL = 24
    GRID_PX = CELL * 9          # 216
    HEADER_H = 22

    CONTROLS = [
        ("Joystick", "WASD", "move"),
        ("Press stick", "Space", "next digit"),
        ("Top button", "U", "next digit"),
        ("Middle button", "J", "erase"),
        ("Bottom button", "M", "prev digit"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        size = min(w, h) - 30
        size -= size % 3
        cell = size // 3
        ox = x + (w - size) // 2
        oy = y + (h - size) // 2
        for i in range(4):
            lw = 2 if i % 3 == 0 else 1
            draw.line((ox, oy + i * cell, ox + size, oy + i * cell), fill=BAND_COLOR, width=lw)
            draw.line((ox + i * cell, oy, ox + i * cell, oy + size), fill=BAND_COLOR, width=lw)
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 16)
        for (r, c, d, color) in [(0, 0, "5", GIVEN_COLOR), (1, 1, "3", ENTRY_COLOR),
                                 (2, 2, "7", GIVEN_COLOR), (0, 2, "1", ENTRY_COLOR)]:
            draw.text((ox + c * cell + cell // 2, oy + r * cell + cell // 2), d,
                      font=font, fill=color, anchor="mm")

    def run(self):
        self.wait_for_release()

        difficulty = self._choose_difficulty()
        if difficulty is None:
            return Destination(BackStackView)

        while True:
            result = self._play_round(difficulty)
            if result is not None:
                return result


    def _choose_difficulty(self):
        options = [ButtonOption("Easy"), ButtonOption("Medium"), ButtonOption("Hard")]
        selected = self.run_screen(
            ButtonListScreen,
            title=_("Sudoku"),
            is_button_text_centered=False,
            show_back_button=True,
            button_data=options,
        )
        self.wait_for_release()
        if selected == RET_CODE__BACK_BUTTON:
            return None
        return ["easy", "medium", "hard"][selected]


    # ------------------------------------------------------------------ round
    def _play_round(self, difficulty):
        self.puzzle_grid = transform(random.choice(PUZZLES[difficulty]))
        self.given = [[v != 0 for v in row] for row in self.puzzle_grid]
        self.grid = [row[:] for row in self.puzzle_grid]
        self.cursor = self._first_empty()
        self.ox = (self.canvas_width - self.GRID_PX) // 2
        self.oy = self.HEADER_H

        # key name -> (constant, repeat?) ; movement repeats, edits don't
        self._held = {}

        while True:
            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()

            if self._is_solved():
                return self._win_screen(difficulty)

            with self.renderer.lock:
                self._render()
                self.renderer.show_image()

            time.sleep(0.03)


    def _first_empty(self):
        for r in range(9):
            for c in range(9):
                if self.grid[r][c] == 0:
                    return [r, c]
        return [0, 0]


    # ------------------------------------------------------------------ input
    def _edge(self, name, key, repeat_delay=None, repeat_rate=0.09) -> bool:
        now = time.time()
        state = self._held.get(name)
        if self.buttons.check_for_low(key):
            if state is None:
                self._held[name] = {"since": now, "last": now}
                return True
            if repeat_delay is not None and now - state["since"] >= repeat_delay \
                    and now - state["last"] >= repeat_rate:
                state["last"] = now
                return True
            return False
        self._held.pop(name, None)
        return False

    def _read_input(self):
        K = HardwareButtonsConstants
        r, c = self.cursor
        if self._edge("up", K.KEY_UP, 0.35):
            self.cursor[0] = (r - 1) % 9
        if self._edge("down", K.KEY_DOWN, 0.35):
            self.cursor[0] = (r + 1) % 9
        if self._edge("left", K.KEY_LEFT, 0.35):
            self.cursor[1] = (c - 1) % 9
        if self._edge("right", K.KEY_RIGHT, 0.35):
            self.cursor[1] = (c + 1) % 9

        r, c = self.cursor
        if self.given[r][c]:
            # Clues can't be edited; consume the edit keys so they don't queue up
            self._edge("press", K.KEY_PRESS)
            self._edge("next", K.KEY1)
            self._edge("erase", K.KEY2)
            self._edge("prev", K.KEY3)
            return

        if self._edge("press", K.KEY_PRESS) or self._edge("next", K.KEY1):
            self.grid[r][c] = (self.grid[r][c] + 1) % 10
        if self._edge("prev", K.KEY3):
            self.grid[r][c] = (self.grid[r][c] - 1) % 10
        if self._edge("erase", K.KEY2):
            self.grid[r][c] = 0


    # ------------------------------------------------------------------ rules
    def _conflicts(self) -> set:
        """Cells whose value duplicates another in its row, column, or box."""
        bad = set()
        for i in range(9):
            self._scan([(i, c) for c in range(9)], bad)
            self._scan([(r, i) for r in range(9)], bad)
        for br in range(3):
            for bc in range(3):
                cells = [(br * 3 + r, bc * 3 + c) for r in range(3) for c in range(3)]
                self._scan(cells, bad)
        return bad

    def _scan(self, cells, bad):
        seen = {}
        for (r, c) in cells:
            v = self.grid[r][c]
            if not v:
                continue
            if v in seen:
                bad.add((r, c))
                bad.add(seen[v])
            else:
                seen[v] = (r, c)

    def _is_solved(self) -> bool:
        if any(0 in row for row in self.grid):
            return False
        return not self._conflicts()


    # ------------------------------------------------------------------ render
    def _render(self):
        draw = self.renderer.draw
        draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill="black")

        cur_r, cur_c = self.cursor
        conflicts = self._conflicts()

        header_font = Fonts.get_font(GUIConstants.get_body_font_name(), 14)
        remaining = sum(row.count(0) for row in self.grid)
        draw.text((6, self.HEADER_H // 2), _("Sudoku"),
                  font=header_font, fill="#aaaaaa", anchor="lm")
        draw.text((self.canvas_width - 6, self.HEADER_H // 2),
                  _("{} left").format(remaining),
                  font=header_font, fill="#aaaaaa", anchor="rm")

        # Highlight the cursor's row/column/box so the eye can follow it
        for r in range(9):
            for c in range(9):
                same_box = (r // 3 == cur_r // 3) and (c // 3 == cur_c // 3)
                if r == cur_r or c == cur_c or same_box:
                    x0 = self.ox + c * self.CELL
                    y0 = self.oy + r * self.CELL
                    draw.rectangle((x0, y0, x0 + self.CELL, y0 + self.CELL), fill=PEER_COLOR)

        # Cursor cell
        x0 = self.ox + cur_c * self.CELL
        y0 = self.oy + cur_r * self.CELL
        draw.rectangle((x0, y0, x0 + self.CELL, y0 + self.CELL),
                       outline=CURSOR_COLOR, width=2)

        # Grid lines (heavier on band boundaries)
        for i in range(10):
            heavy = (i % 3 == 0)
            color = BAND_COLOR if heavy else GRID_COLOR
            width = 2 if heavy else 1
            x = self.ox + i * self.CELL
            y = self.oy + i * self.CELL
            draw.line((self.ox, y, self.ox + self.GRID_PX, y), fill=color, width=width)
            draw.line((x, self.oy, x, self.oy + self.GRID_PX), fill=color, width=width)

        # Digits
        digit_font = Fonts.get_font(GUIConstants.get_body_font_name(), 17)
        for r in range(9):
            for c in range(9):
                v = self.grid[r][c]
                if not v:
                    continue
                if (r, c) in conflicts:
                    color = CONFLICT_COLOR
                elif self.given[r][c]:
                    color = GIVEN_COLOR
                else:
                    color = ENTRY_COLOR
                draw.text((self.ox + c * self.CELL + self.CELL // 2,
                           self.oy + r * self.CELL + self.CELL // 2),
                          str(v), font=digit_font, fill=color, anchor="mm")


    # ------------------------------------------------------------------ end
    def _win_screen(self, difficulty):
        self.wait_for_release()
        AGAIN = ButtonOption("New puzzle")
        QUIT = ButtonOption("Quit")
        button_data = [AGAIN, QUIT]
        selected = self.run_screen(
            LargeIconStatusScreen,
            title=_("Solved!"),
            status_headline=_("Nice."),
            text=_("You finished a {} puzzle.").format(_(difficulty)),
            button_data=button_data,
            show_back_button=False,
        )
        if button_data[selected] == AGAIN:
            self.wait_for_release()
            return None
        return Destination(BackStackView)
