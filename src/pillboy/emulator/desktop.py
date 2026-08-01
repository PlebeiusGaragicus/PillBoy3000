"""
    Desktop emulation backend: a tkinter window stands in for the ST7789 display and
    the keyboard stands in for the Waveshare HAT's joystick + buttons.

    tkinter must run on the *main* thread (hard requirement on macOS), so the emulator
    inverts the app's usual structure: `DesktopEmulator.run()` owns the main thread and
    tk mainloop, while the PillBoy Controller loop runs in a daemon thread. Frames are
    handed off via `submit_frame()` and painted by a tk `after()` polling loop, so no
    tk call ever happens off the main thread.

    Keys: WASD = joystick, Space = joystick press, U/J/M = top/middle/bottom side buttons.
"""
import logging
import os
import threading
import tkinter as tk

from PIL import Image, ImageTk

from pillboy.hardware.displays.display_driver import BaseDisplayDriver
from pillboy.hardware.gpio import GPIO

logger = logging.getLogger(__name__)

_emulator = None


def get_emulator() -> "DesktopEmulator":
    global _emulator
    if _emulator is None:
        _emulator = DesktopEmulator()
    return _emulator


class DesktopEmulator:
    SCALE = 2           # 240x240 is tiny on a modern desktop; render 2x
    FRAME_POLL_MS = 16  # ~60Hz paint loop


    def __init__(self):
        self._latest_frame: Image.Image = None
        self._frame_lock = threading.Lock()
        self.root = None


    def submit_frame(self, image: Image.Image):
        """Called from the app thread; just stores the frame for the tk paint loop."""
        with self._frame_lock:
            self._latest_frame = image.copy()


    def run(self, app_target):
        """
            Must be called on the main thread. Builds the window, starts `app_target`
            in a daemon thread, then blocks in tk's mainloop until the window closes.
        """
        from pillboy.hardware.buttons import HardwareButtons

        # WASD = joystick, Space = center-stick press, U/J/M = top/middle/bottom side buttons
        keymap = {
            "w": HardwareButtons.KEY_UP_PIN,
            "s": HardwareButtons.KEY_DOWN_PIN,
            "a": HardwareButtons.KEY_LEFT_PIN,
            "d": HardwareButtons.KEY_RIGHT_PIN,
            "space": HardwareButtons.KEY_PRESS_PIN,
            "u": HardwareButtons.KEY1_PIN,
            "j": HardwareButtons.KEY2_PIN,
            "m": HardwareButtons.KEY3_PIN,
        }

        self.root = tk.Tk()
        self.root.title("PillBoy3000 emulator")
        self.root.resizable(width=False, height=False)
        self.root.configure(bg="black")

        self.label = tk.Label(self.root, bg="black", borderwidth=0, highlightthickness=0)
        self.label.pack()

        def on_key_press(event):
            pin = keymap.get(event.keysym)
            if pin is not None:
                GPIO.press(pin)

        def on_key_release(event):
            pin = keymap.get(event.keysym)
            if pin is not None:
                GPIO.release(pin)

        def on_close():
            # The app loop is a daemon thread blocked on GPIO polling; just exit hard.
            logger.info("Emulator window closed; exiting")
            os._exit(0)

        self.root.bind("<KeyPress>", on_key_press)
        self.root.bind("<KeyRelease>", on_key_release)
        self.root.protocol("WM_DELETE_WINDOW", on_close)

        app_thread = threading.Thread(target=app_target, daemon=True)
        app_thread.start()

        self._paint()
        self.root.mainloop()


    def _paint(self):
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None

        if frame is not None:
            if self.SCALE != 1:
                frame = frame.resize(
                    (frame.width * self.SCALE, frame.height * self.SCALE),
                    Image.NEAREST)
            self._tkimage = ImageTk.PhotoImage(frame, master=self.root)
            self.label.configure(image=self._tkimage)

        self.root.after(self.FRAME_POLL_MS, self._paint)



class DesktopDisplay(BaseDisplayDriver):
    """Display driver that forwards frames to the emulator window."""
    display_type = "desktop"

    def show_image(self, image, x_start: int = 0, y_start: int = 0):
        get_emulator().submit_frame(image)
