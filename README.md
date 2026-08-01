# PillBoy3000

A tiny, silent, toy-like handheld game console built from SeedSigner-class hardware:
Raspberry Pi Zero 1.3 + Waveshare 1.3" 240x240 LCD HAT (joystick + 3 buttons) + Pi
camera. The device boots from RAM in seconds off a read-only microSD card — no writes,
no saves, safe to cut power at any moment.

The app is a stripped-down fork of [SeedSigner](https://github.com/SeedSigner/seedsigner)
(controller / views / PIL-based GUI / ST7789 + GPIO hardware layer preserved; all
Bitcoin functionality removed) with a game picker menu and a `pillboy/games/` package.

OS images are built by the sibling **PillBoy3000-os** repo (Buildroot, modeled on
[seedsigner-os](https://github.com/SeedSigner/seedsigner-os)).

## Run on desktop (emulator)

The desktop backend is built in — a tkinter window stands in for the LCD and the
keyboard for the buttons. No hardware needed:

The venv's python must include tkinter. On macOS, Homebrew's default `python3` does
NOT — install `brew install python-tk@3.11` and build the venv with `python3.11`.
Verify with: `python3.11 -c "import tkinter"` (no output = good).

```sh
# --- SETUP VENV
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# --- RUN
cd src
python3 main.py
```

The only desktop dependency is Pillow.

Keys: **WASD** = joystick, **Space** = joystick center press, **U/J/M** = the three
side buttons (top/middle/bottom).

## Run on hardware

Flash a PillBoy3000-os image (see that repo). For development, flash a `-dev` image,
connect the Pi Zero's data micro-USB port to your Mac (one cable = power + network),
and use `dev.sh` — the app auto-detects real hardware (RPi.GPIO present) and drives
the ST7789 over SPI. One-time SSH setup instructions are in the `dev.sh` header.

```sh
./dev.sh sync --restart    # push working tree to the device and relaunch the app
./dev.sh logs -f           # follow the app log live
./dev.sh screenshot        # capture the device screen to ./screenshot.png
./dev.sh shell             # SSH in
./dev.sh status            # pillboy start|stop|restart|status
```

## Layout

```
src/main.py                  entry point (desktop emulator vs hardware autodetect)
src/pillboy/controller.py    main loop: View in, Destination out
src/pillboy/views/           navigation logic (game picker, power, errors)
src/pillboy/games/           one module per game + GAMES registry
src/pillboy/gui/             PIL rendering: components, screens, renderer
src/pillboy/hardware/        buttons (GPIO), camera, displays, platform detect
src/pillboy/emulator/        desktop backend (tkinter display + keyboard GPIO)
```

## Adding a game

1. Create `src/pillboy/games/mygame.py` with a `GameView` subclass (see
   `games/base.py`) whose `run()` owns its game loop — see `bounce.py` for the
   reference shape. Every button including the three side buttons belongs to
   gameplay; the one reserved input is **all three side buttons pressed together**,
   which opens the shared pause menu (Resume / Quit game). Your loop must:
   - start with `self.wait_for_release()` (debounce the launch press)
   - call `dest = self.check_pause_menu()` once per frame and return `dest` if set
   - claim `self.renderer.lock` per frame around draw + show, never across frames
2. Register it in the `GAMES` list in `src/pillboy/games/__init__.py`.
