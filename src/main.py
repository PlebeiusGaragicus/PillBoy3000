#!/usr/bin/env python

import argparse
import logging
import sys

logger = logging.getLogger(__name__)

DEFAULT_MODULE_LOG_LEVELS = {
    "PIL": logging.WARNING,
    # "pillboy.gui.toast": logging.DEBUG,  # example of more specific submodule logging config
}


def main(sys_argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--loglevel",
        choices=list((logging._nameToLevel.keys())),
        default="INFO",
        type=str,
        help="Set the log level (default: %(default)s)",
    )

    args = parser.parse_args(sys_argv)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.getLevelName(args.loglevel))
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)8s [%(name)s %(funcName)s (%(lineno)d)]: %(message)s")
    )
    root_logger.addHandler(console_handler)

    # Set log levels for specific modules
    for module, level in DEFAULT_MODULE_LOG_LEVELS.items():
        logging.getLogger(module).setLevel(level)

    logger.info(f"Starting PillBoy with: {args.__dict__}")

    # SIGUSR2 dumps the current canvas to a PNG. The ST7789 is write-only over SPI,
    # so this is the only way to "screenshot" a live device (used by dev.sh screenshot).
    import signal

    def dump_screenshot(signum, frame):
        try:
            from pillboy.gui.renderer import Renderer
            path = "/tmp/pillboy-screenshot.png"
            Renderer.get_instance().canvas.save(path)
            logger.info(f"Screenshot saved to {path}")
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")

    signal.signal(signal.SIGUSR2, dump_screenshot)

    from pillboy.controller import Controller
    from pillboy.hardware.platform import is_raspberry_pi

    if is_raspberry_pi():
        # Get the one and only Controller instance and start our main loop
        Controller.get_instance().start()
    else:
        # Desktop emulation: tkinter owns the main thread (a macOS requirement);
        # the Controller loop runs in a daemon thread.
        from pillboy.emulator.desktop import get_emulator
        get_emulator().run(lambda: Controller.get_instance().start())


if __name__ == "__main__":
    main(sys.argv[1:])
