"""
    Single import point for GPIO access.

    On real Pi hardware this is just RPi.GPIO. On a desktop it's a virtual GPIO whose
    "pins" are driven by the emulator window's keyboard/button events, so all of the
    level-polling code in `buttons.py` runs unchanged.
"""


class VirtualGPIO:
    # Report a 40-pin header so HardwareButtons picks the standard pin numbers
    RPI_INFO = {'P1_REVISION': 3}

    LOW = 0
    HIGH = 1
    OUT = 2
    IN = 3
    PUD_OFF = 4
    PUD_DOWN = 5
    PUD_UP = 6
    BCM = 7
    BOARD = 101

    def __init__(self):
        self._pressed = set()

    def setmode(self, mode):
        pass

    def setwarnings(self, flag):
        pass

    def setup(self, channel, state, initial=-1, pull_up_down=-1):
        pass

    def cleanup(self):
        pass

    def input(self, channel):
        # Pins are pulled up; pressed == LOW, matching the real hardware
        return self.LOW if channel in self._pressed else self.HIGH

    # --- emulator-side API (not part of RPi.GPIO) ---
    def press(self, pin):
        self._pressed.add(pin)

    def release(self, pin):
        self._pressed.discard(pin)


try:
    import RPi.GPIO as GPIO  # noqa: N814
except Exception:
    GPIO = VirtualGPIO()
