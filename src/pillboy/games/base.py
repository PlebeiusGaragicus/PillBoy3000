import time

from dataclasses import dataclass
from gettext import gettext as _
from typing import Callable

from pillboy.gui.components import Fonts, GUIConstants, SeedSignerIconConstants
from pillboy.gui.screens import RET_CODE__BACK_BUTTON
from pillboy.gui.screens.screen import ButtonListScreen, ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtons, HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination, View


@dataclass
class GameTitleScreen(ButtonListScreen):
    """ButtonListScreen with a game thumbnail drawn in the space above the buttons."""
    thumbnail_renderer: Callable = None

    def __post_init__(self):
        self.is_bottom_list = True
        super().__post_init__()

    def _render(self):
        super()._render()
        if self.thumbnail_renderer:
            # Region between the top nav and the bottom-anchored buttons
            top = self.top_nav.height + 4
            bottom = self.canvas_height - (2 * GUIConstants.BUTTON_HEIGHT
                                           + GUIConstants.LIST_ITEM_PADDING
                                           + GUIConstants.EDGE_PADDING + 8)
            self.thumbnail_renderer(self.image_draw, 0, top, self.canvas_width, bottom - top)



@dataclass
class GameWelcomeView(View):
    """
        Per-game title screen: game name in the top nav, a small graphic, and
        Play / How-to buttons (plus the standard back button to the picker).
    """
    game_index: int = 0

    PLAY = ButtonOption("Play")
    HOW_TO = ButtonOption("How-to")

    def run(self):
        from pillboy.games import GAMES
        entry = GAMES[self.game_index]

        button_data = [self.PLAY, self.HOW_TO]
        selected_menu_num = self.run_screen(
            GameTitleScreen,
            title=entry.display_name,
            button_data=button_data,
            show_back_button=True,
            thumbnail_renderer=getattr(entry.View_cls, "render_thumbnail", None),
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if button_data[selected_menu_num] == self.PLAY:
            return Destination(entry.View_cls)

        return Destination(GameHowToView, view_args=dict(game_index=self.game_index))



@dataclass
class GameHowToView(View):
    """
        Button-mapping screen for one game, built from the game class's CONTROLS
        list of (hardware_label, keyboard_hint, action) tuples. The pause combo
        line is appended automatically. Any button returns to the title screen.
    """
    game_index: int = 0

    def run(self):
        from pillboy.games import GAMES
        from pillboy.hardware.platform import is_raspberry_pi

        entry = GAMES[self.game_index]
        controls = list(getattr(entry.View_cls, "CONTROLS", []))
        controls.append((_("3 side btns together"), "U+J+M", _("pause")))

        show_kb = not is_raspberry_pi()
        draw = self.renderer.draw
        title_font = Fonts.get_font(GUIConstants.get_top_nav_title_font_name(), 18)
        body_font = Fonts.get_font(GUIConstants.get_body_font_name(), 14)
        hint_font = Fonts.get_font(GUIConstants.get_body_font_name(), 12)
        ACCENT = GUIConstants.ACCENT_COLOR

        with self.renderer.lock:
            draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill="black")
            draw.text((self.canvas_width // 2, 8), entry.display_name,
                      font=title_font, fill=ACCENT, anchor="mt")

            y = 44
            for (label, kb_hint, action) in controls:
                if show_kb and kb_hint:
                    label = f"{label} ({kb_hint})"
                draw.text((8, y), label, font=body_font, fill="white", anchor="lm")
                draw.text((self.canvas_width - 8, y), action,
                          font=body_font, fill="#aaaaaa", anchor="rm")
                y += 24

            draw.text((self.canvas_width // 2, self.canvas_height - 4),
                      _("press any button"), font=hint_font, fill=ACCENT, anchor="ms")
            self.renderer.show_image()

        buttons = HardwareButtons.get_instance()
        buttons.wait_for(HardwareButtonsConstants.ALL_KEYS)
        while buttons.has_any_input():
            time.sleep(0.01)

        return Destination(BackStackView)



class GameView(View):
    """
        Base class for all games.

        Games own their run() loop and poll HardwareButtons directly — all buttons
        (including the three side buttons) belong to gameplay. The one reserved input
        is the PAUSE_COMBO: all three side buttons pressed simultaneously opens the
        shared pause menu (Resume / Quit game).

        A game's loop must:
        * call `dest = self.check_pause_menu()` once per frame and `return dest` if
          it's not None (the player chose "Quit game")
        * claim `self.renderer.lock` per frame around draw + show, never across
          frames (the pause menu and overlay threads need to acquire it)
    """
    PAUSE_COMBO = [
        HardwareButtonsConstants.KEY1,
        HardwareButtonsConstants.KEY2,
        HardwareButtonsConstants.KEY3,
    ]

    RESUME = ButtonOption("Resume")
    QUIT = ButtonOption("Quit game")


    def _initialize(self):
        super()._initialize()
        self.buttons = HardwareButtons.get_instance()


    def wait_for_release(self):
        """ Block until no buttons are pressed (debounce transitions in/out of games). """
        while self.buttons.has_any_input():
            time.sleep(0.01)


    def check_pause_menu(self) -> Destination | None:
        """
            Call once per game-loop frame. Returns None to keep playing, or a
            Destination (back to the menu) when the player quits.
        """
        if not self.buttons.all_pressed(self.PAUSE_COMBO):
            return None

        # Don't let the combo presses leak into the pause menu or back into the game
        self.wait_for_release()

        button_data = [self.RESUME, self.QUIT]
        selected_menu_num = self.run_screen(
            LargeIconStatusScreen,
            title=_("Paused"),
            status_icon_name=SeedSignerIconConstants.WARNING,
            status_color=GUIConstants.ACCENT_COLOR,
            status_headline=None,
            text=_("...or are you spazz-ing? ;)"),
            button_data=button_data,
            show_back_button=False,
        )

        if button_data[selected_menu_num] == self.QUIT:
            return Destination(BackStackView)

        # Resume: swallow the selection press, then hand control back to the game
        self.wait_for_release()
        return None
