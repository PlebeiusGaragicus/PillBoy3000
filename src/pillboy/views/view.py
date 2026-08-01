import logging
from dataclasses import dataclass
from gettext import gettext as _
from typing import Type

from pillboy.helpers.l10n import mark_for_translation as _mft
from pillboy.gui.components import SeedSignerIconConstants
from pillboy.gui.screens import RET_CODE__POWER_BUTTON, RET_CODE__BACK_BUTTON
from pillboy.gui.screens.screen import BaseScreen, ButtonListScreen, ButtonOption, LargeButtonScreen, WarningScreen, ErrorScreen
from pillboy.models.settings import Settings, SettingsConstants
from pillboy.models.threads import BaseThread

logger = logging.getLogger(__name__)



class BackStackView:
    """
        Empty class that just signals to the Controller to pop the most recent View off
        the back_stack.
    """
    pass



"""
    Views contain the biz logic to handle discrete tasks, exactly analogous to a Flask
    request/response function or a Django View. Each page/screen displayed to the user
    should be implemented in its own View.

    In a web context, the View would prepare data for the html/css/js presentation
    templates. We have to implement our own presentation layer (implemented as `Screen`
    objects). For the sake of code cleanliness and separation of concerns, the View code
    should not know anything about pixel-level rendering.

    Sequences that require multiple pages/screens should be implemented as a series of
    separate Views. Exceptions can be made for complex interactive sequences, but in
    general, if your View is instantiating multiple Screens, you're probably putting too
    much functionality in that View.

    As with http requests, Views can receive input vars to inform their behavior. Views
    can also prepare the next set of vars to set up the next View that should be
    displayed (akin to Flask's `return redirect(url, param1=x, param2=y))`).
"""
class View:
    def _initialize(self):
        """
        Whether the View is a regular class initialized by __init__() or a dataclass
        initialized by __post_init__(), this method will be called to set up the View's
        instance variables.
        """
        # Import here to avoid circular imports
        from pillboy.controller import Controller
        from pillboy.gui import Renderer

        self.controller: Controller = Controller.get_instance()
        self.settings = Settings.get_instance()

        self.renderer = Renderer.get_instance()
        self.canvas_width = self.renderer.canvas_width
        self.canvas_height = self.renderer.canvas_height

        self.screen = None

        self._redirect: 'Destination' = None
        self.is_screensaver_allowed = True


    def __init__(self):
        self._initialize()


    def __post_init__(self):
        self._initialize()


    @property
    def has_redirect(self) -> bool:
        if not hasattr(self, '_redirect'):
            # Easy for a View to forget to call super().__init__()
            raise Exception(f"{self.__class__.__name__} did not call super().__init__()")
        return self._redirect is not None


    def set_redirect(self, destination: 'Destination'):
        """
        Enables early `__init__()` / `__post_init__()` logic to redirect away from the
        current View.

        Set a redirect Destination and then immediately `return` to exit `__init__()` or
        `__post_init__()`. When the `Destination.run()` is called, it will see the redirect
        and immediately return that new Destination to the Controller without running
        the View's `run()`.
        """
        # Always insure skip_current_view is set for a redirect
        destination.skip_current_view = True
        self._redirect = destination


    def get_redirect(self) -> 'Destination':
        return self._redirect


    def run_screen(self, Screen_cls: Type[BaseScreen], **kwargs) -> int | str:
        """
            Instantiates the provided Screen_cls and runs its interactive display.
            Returns the user's input upon completion.
        """
        self.screen = Screen_cls(**kwargs)
        return self.screen.display()


    def run(self, **kwargs) -> 'Destination':
        raise Exception("Must implement in the child class")



@dataclass
class Destination:
    """
        Basic struct to pass back to the Controller to tell it which View the user should
        be presented with next.
    """
    View_cls: Type[View]                # The target View to route to
    view_args: dict = None              # The input args required to instantiate the target View
    skip_current_view: bool = False     # The current View is just forwarding; omit current View from history
    clear_history: bool = False         # Optionally clears the back_stack to prevent "back"


    def __repr__(self):
        if self.View_cls is None:
            out = "None"
        else:
            out = self.View_cls.__name__
        if self.view_args:
            out += f"({self.view_args})"
        else:
            out += "()"
        if self.clear_history:
            out += f" | clear_history: {self.clear_history}"
        return out


    def _instantiate_view(self):
        if not self.view_args:
            # Can't unpack (**) None so we replace with an empty dict
            self.view_args = {}

        # Instantiate the `View_cls` with the `view_args` dict
        self.view = self.View_cls(**self.view_args)


    def _run_view(self):
        if self.view.has_redirect:
            return self.view.get_redirect()
        return self.view.run()


    def run(self):
        self._instantiate_view()
        return self._run_view()


    def __eq__(self, obj):
        """
            Equality test IGNORES the skip_current_view and clear_history options
        """
        return (isinstance(obj, Destination) and
            obj.View_cls == self.View_cls and
            obj.view_args == self.view_args)


    def __ne__(self, obj):
        return not obj == self



#########################################################################################
#
# Root level Views don't have a sub-module home so they live at the top level here.
#
#########################################################################################
class WelcomeView(View):
    """
        Shown once after the boot splash: a quick diagram of the controls.
        Any button dismisses it.
    """
    def run(self):
        import time
        from pillboy.gui.components import Fonts, GUIConstants
        from pillboy.hardware.buttons import HardwareButtons, HardwareButtonsConstants
        from pillboy.hardware.platform import is_raspberry_pi

        buttons = HardwareButtons.get_instance()
        draw = self.renderer.draw

        title_font = Fonts.get_font(GUIConstants.get_top_nav_title_font_name(), 20)
        body_font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        hint_font = Fonts.get_font(GUIConstants.get_body_font_name(), 12)

        ACCENT = GUIConstants.ACCENT_COLOR
        GRAY = "#aaaaaa"

        with self.renderer.lock:
            draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill="black")
            draw.text((self.canvas_width // 2, 10), _("Welcome to PillBoy"),
                      font=title_font, fill=ACCENT, anchor="mt")

            rows_y = [56, 96, 136, 176]
            glyph_cx = 34
            text_x = 68

            # Row 1: joystick d-pad cross = move
            cy = rows_y[0]
            draw.rectangle((glyph_cx - 5, cy - 15, glyph_cx + 5, cy + 15), fill="#444444")
            draw.rectangle((glyph_cx - 15, cy - 5, glyph_cx + 15, cy + 5), fill="#444444")
            draw.text((text_x, cy), _("Joystick: move"), font=body_font, fill="white", anchor="lm")

            # Row 2: center press = select
            cy = rows_y[1]
            draw.ellipse((glyph_cx - 9, cy - 9, glyph_cx + 9, cy + 9), fill=ACCENT)
            draw.text((text_x, cy), _("Press stick: select"), font=body_font, fill="white", anchor="lm")

            # Row 3: three side buttons = game actions
            cy = rows_y[2]
            for i in range(3):
                by = cy - 15 + i * 11
                draw.rounded_rectangle((glyph_cx - 12, by, glyph_cx + 12, by + 8),
                                       radius=3, fill="#444444")
            draw.text((text_x, cy), _("Side buttons: actions"), font=body_font, fill="white", anchor="lm")

            # Row 4: all three together = pause
            cy = rows_y[3]
            for i in range(3):
                by = cy - 15 + i * 11
                draw.rounded_rectangle((glyph_cx - 12, by, glyph_cx + 12, by + 8),
                                       radius=3, fill=ACCENT)
            draw.text((text_x, cy), _("All 3 together: pause"), font=body_font, fill="white", anchor="lm")

            if not is_raspberry_pi():
                hint = _("(keys: WASD / Space / U J M)")
                draw.text((self.canvas_width // 2, 206), hint,
                          font=hint_font, fill=GRAY, anchor="mt")

            draw.text((self.canvas_width // 2, self.canvas_height - 4),
                      _("press any button"),
                      font=hint_font, fill=ACCENT, anchor="ms")

            self.renderer.show_image()

        buttons.wait_for(HardwareButtonsConstants.ALL_KEYS)
        while buttons.has_any_input():
            time.sleep(0.01)

        return Destination(MainMenuView, clear_history=True)



class MainMenuView(View):
    """
        The game picker: one button per registered game.
    """
    def run(self):
        from pillboy.games import GAMES

        button_data = [ButtonOption(game.display_name) for game in GAMES]
        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("PillBoy"),
            is_button_text_centered=False,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__POWER_BUTTON:
            return Destination(PowerOptionsView)

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            # Nothing to go back to from Home; just re-run
            return Destination(MainMenuView)

        from pillboy.games.base import GameWelcomeView
        return Destination(GameWelcomeView, view_args=dict(game_index=selected_menu_num))



class PowerOptionsView(View):
    RESET = ButtonOption("Restart", SeedSignerIconConstants.RESTART)
    POWER_OFF = ButtonOption("Power off", SeedSignerIconConstants.POWER)

    def run(self):
        button_data = [self.RESET, self.POWER_OFF]
        selected_menu_num = self.run_screen(
            LargeButtonScreen,
            title=_("Reset / Power"),
            show_back_button=True,
            button_data=button_data
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_num] == self.RESET:
            return Destination(RestartView)

        elif button_data[selected_menu_num] == self.POWER_OFF:
            return Destination(PowerOffView)


@dataclass
class RestartView(View):

    def run(self):
        from pillboy.gui.screens.screen import ResetScreen

        if not self.renderer.is_screenshot_generator:
            # We don't want the screenshot generator to actually try to do the restart
            RestartView.DoResetThread().start()

        self.run_screen(ResetScreen)


    class DoResetThread(BaseThread):
        def run(self):
            import os
            import sys
            import time

            logger.info("Restarting PillBoy")
            # Give the screen just enough time to display the reset message before
            # exiting.
            time.sleep(0.25)

            # Flush any buffered data.
            sys.stdout.flush()
            sys.stderr.flush()

            # Replace the current process with a new one.
            os.execv(sys.executable, [sys.executable] + sys.argv)



class PowerOffView(View):
    def run(self):
        from pillboy.gui.screens.screen import PowerOffNotRequiredScreen
        self.run_screen(PowerOffNotRequiredScreen)
        return Destination(BackStackView)



@dataclass
class NotYetImplementedView(View):
    """
        Temporary View to use during dev.
    """
    text: str = _mft("This is still on our to-do list!")


    def run(self):
        self.run_screen(
            WarningScreen,
            title=_("Work In Progress"),
            status_headline=_("Not Yet Implemented"),
            text=self.text,
            button_data=[ButtonOption("Back to main menu")],
        )

        return Destination(MainMenuView)



@dataclass
class ErrorView(View):
    title: str = _mft("Error")
    show_back_button: bool = True
    status_icon_name: str = SeedSignerIconConstants.ERROR
    status_headline: str = None
    text: str = None
    button_text: str = None
    next_destination: Destination = None

    def run(self):
        self.run_screen(
            ErrorScreen,
            title=self.title,
            status_icon_name=self.status_icon_name,
            status_headline=self.status_headline,
            text=self.text,
            button_data=[ButtonOption(self.button_text)],
            show_back_button=self.show_back_button,
        )
        return self.next_destination if self.next_destination else Destination(MainMenuView, clear_history=True)



@dataclass
class UnhandledExceptionView(View):
    error: list[str]

    def __post_init__(self):
        from pillboy.hardware.camera import CameraConnectionError
        super().__post_init__()

        # Camera errors bubble up to here. Reroute to their custom error View.
        if self.error[0] == CameraConnectionError.__name__:
            self.set_redirect(
                Destination(
                    CameraConnectionErrorView,
                    skip_current_view=True,
                )
            )


    def run(self):
        self.run_screen(
            ErrorScreen,
            title=_("System Error"),
            status_headline=self.error[0],
            text=self.error[1] + "\n" + self.error[2],
            button_data=[ButtonOption("Back to Main Menu")],
        )

        return Destination(MainMenuView, clear_history=True)



@dataclass
class CameraConnectionErrorView(View):
    def run(self):
        self.run_screen(
            ErrorScreen,
            title=_("Hardware Error"),
            status_headline=_("Cannot access camera"),
            text=_("Disconnect power and check for a loose camera connection."),
            button_data=[ButtonOption("Back to Main Menu")],
            show_back_button=False,
        )

        return Destination(MainMenuView, clear_history=True)
