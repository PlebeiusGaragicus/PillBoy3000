# TODO / Roadmap

PillBoy3000 = a silent, toy-like handheld game console on a Raspberry Pi Zero 1.3 +
Waveshare 1.3" 240x240 LCD HAT (joystick + 3 side buttons) + Pi camera. The OS boots
100% from RAM in seconds off a read-only microSD (no writes ever, safe to yank power).
One card carries the whole game library behind a picker menu. The app is a stripped
seedsigner fork (PIL rendering now; pygame trialed later). Sibling repo
`../PillBoy3000-os` builds the microSD images (Buildroot, adapted from seedsigner-os).
Workspace map and conventions: see `../AGENTS.md`.

## Phase 1 — Stub app + desktop emulator ✅ DONE

Stripped seedsigner fork boots to a game-picker menu with a Bounce demo game; runs on
desktop via the built-in tkinter emulator (`cd src && python3 main.py`; WASD = joystick,
Space = center press, U/J/M = side buttons). Venv needs a tkinter-capable python
(macOS: `brew install python-tk@3.11`). Only dependency: Pillow.

## Phase 2 — OS repo + dev loop ✅ DONE (authored, NOT yet build-tested)

`../PillBoy3000-os` adapted from seedsigner-os (pi0 + pi0-dev only, Bitcoin packages
stripped, pillboy branding/hostname/service names). `./dev.sh` in this repo gives
sync/restart/logs/screenshot/shell against a dev device at `pillboy.local`.
`main.py` dumps a screenshot on SIGUSR2 (that's how `dev.sh screenshot` works).

## Phase 2.5 — First real image build ⏳ NEXT HARDWARE STEP (needs Docker + ~1-3h)

Nothing below is verified yet; expect to iterate on build errors (that's normal for
Buildroot config adaptations).

- [ ] In `../PillBoy3000-os`: add the buildroot submodule (one-time):
      `git submodule add https://github.com/seedsigner/buildroot opt/buildroot`
      `git submodule update --init`   (then commit the submodule)
- [ ] Build a dev image: `PB_ARGS="--pi0 --dev" docker compose up --build`
      (clones the app from the bind-mounted `../PillBoy3000` checkout, branch `main`).
      For iterating: `PB_ARGS="--no-op" docker compose up -d`, then
      `docker exec -it <container> bash` and `./build.sh --pi0 --dev --no-clean`.
- [ ] Flash `images/pillboy_os.main.pi0-dev.img` to a microSD (Raspberry Pi Imager /
      balenaEtcher / dd), boot the Pi Zero 1.3 with the Waveshare HAT.
- [ ] Connect Pi's *data* micro-USB port to the Mac (one cable = power + USB-ethernet),
      enable macOS Internet Sharing for the RNDIS gadget, then follow the one-time SSH
      setup in the `dev.sh` header. Verify: `ssh root@pillboy.local` (password `pillboy`).
- [ ] Verify the dev loop end to end: `./dev.sh sync --restart`, `./dev.sh logs -f`,
      `./dev.sh screenshot`, and confirm the menu + Bounce run on the real screen.
- [ ] Test the QR loader on hardware: open `../PillBoyQR/index.html`,
      generate the example game, and scan it with the device's camera (Scan QR in
      the menu). This is the only untested path in the QR feature — tune
      `QRScanView.FPS`, camera resolution, and generator frame rate if it struggles.
- [ ] Build + flash + boot a release image (`PB_ARGS="--pi0"`): confirm fast boot,
      confirm the card is never written, confirm no networking exists.
- [ ] Measure and note: boot time, Bounce frame rate on hardware (PIL over SPI).

## Phase 3 — Release image hardening & the "toy" experience

- [ ] Splash-to-menu time budget: trim slow imports / defer camera stack.
- [ ] Games load from the card's FAT partition into RAM at boot (games-as-data), so
      adding a game = copying files to the card, not rebuilding the zImage.
- [ ] Decide poweroff story (release image has no power button UI need? PowerOffView
      currently says "just cut power" — verify that message fits the toy concept).
- [ ] re-branch `logo_black_240.png` (splash + screensaver still show SeedSigner logo);
      also rename `SeedSignerIconConstants` and regenerate/replace the icon font.
- [ ] Trim dead code inherited from seedsigner as it surfaces (keyboard.py, microsd
      toasts, unused gui components).

## Phase 4 — Real games + camera + pygame experiment

- [x] Input conventions: all buttons belong to gameplay; all-three-side-buttons combo
      opens the shared pause menu (Resume / Quit game) — `games/base.py` GameView.
- [x] First real game: Tetris (`games/tetris.py`) — 7-bag, wall kicks, scoring/levels,
      next-piece preview, game-over screen. Verify frame rate on real hardware.
- [x] Snake (`games/snake.py`) — absolute + relative steering, speed-up per food,
      "push to start" ready state, game-over screen.
- [x] Sudoku (`games/sudoku.py`) — completes the classic "decoy game" trio from
      seedsigner's old roadmap. 9 verified-unique base puzzles at 3 difficulties,
      randomized at runtime by isomorphic transform (no slow generator on-device).
- [x] Star Fighter (`games/starfighter.py`) — 3 levels: Galaga-style squadron
      (curved fly-in, formation, dives), asteroid field, boss with a weak point
      per cannon + health bar.
- [x] Snek (`games/snek.py`) — port of an old pygame prototype's ergonomics
      (wrapping edges, constant speed, self-collision only); rotation steering
      and rounded gradient art to keep it distinct from `snake.py`.
- [x] Ported the 2023 card's games (`../PillBoy2023-sdcard`): Snek 1, Warp Snek,
      Grubs, Star Saver (with its original PNG art). "1" = 2023 original,
      "2" = written for PillBoy3000.
- [ ] More games as inspiration strikes.
- [ ] Possible: revive the 2023 card's manifest-driven module system for
      games-as-data on the FAT partition (see Phase 3).
- [x] QR loader: scan an animated QR to load a game / message / picture into RAM
      (`pillboy/qrload/`, PB1 protocol; generator webapp in `../PillBoyQR`).
      Protocol + dynamic game loading verified incl. real optical decode; the
      on-device camera scan path is UNTESTED until hardware (see Phase 2.5).
- [ ] Camera game experiment (camera module + pivideostream are kept in the app;
      desktop camera backend is NOT implemented — emulator would need an
      opencv/webcam stand-in first; that would also let QRScanView be tested
      on desktop).
- [ ] pygame branch: swap PIL rendering for pygame Surfaces blitted to the ST7789
      (desktop gets a real pygame window for free). Measure frame rate vs PIL on
      hardware; migrate only if it clearly wins. Needs SDL added to the OS image.

## Phase 5 — Polish / stretch

- [ ] Screensaver rebrand (bouncing PillBoy logo).
- [x] Game metadata: per-game icons in the picker (`GameEntry.icon_name`).
- [ ] High-score-free design language: games should be session-based by design (no
      persistence exists on release images, by intent).
- [ ] Multi-card "library" workflow docs: how to master a new card (flash release
      image + copy game files).
- [ ] Emulator niceties: window title shows current view, keyboard help overlay,
      `--scale` flag (SCALE constant exists in `pillboy/emulator/desktop.py`).

## Known quirks / context for a fresh session

- Desktop run needs tkinter-capable python (macOS: python3.11 via python-tk@3.11).
- The emulator keymap is lowercase-keysym only (Caps Lock breaks input).
- Games must wait for button release on entry and around the pause menu (GameView
  handles this: `wait_for_release()` / `check_pause_menu()`) or held presses leak
  between menu and game and they ping-pong instantly.
- Games claim `renderer.lock` per frame only — `Screen.display()` (pause menu) needs
  to acquire it, so holding it across frames deadlocks.
- `Settings.HOSTNAME == "pillboy-os"` gates on-device behaviors (settings path).
- seedsigner upstream repos live in this workspace as read-only reference; the
  emulator concept came from `../seedsigner-emulator` (abandoned, don't copy code).
