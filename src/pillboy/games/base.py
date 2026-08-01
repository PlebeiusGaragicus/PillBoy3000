import time

from gettext import gettext as _

from pillboy.gui.components import GUIConstants, SeedSignerIconConstants
from pillboy.gui.screens.screen import ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtons, HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination, View


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
