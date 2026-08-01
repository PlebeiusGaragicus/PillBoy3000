"""
    Turns received PB1 payloads into live objects.

    NOTE: "game" payloads are arbitrary python executed on the device — that is
    the entire point of the feature (scan code, play it). There is no sandbox.
    On a release image nothing persists: a loaded game lives in RAM and is gone
    at power-off.
"""
import logging

from pillboy.games import GAMES, GameEntry
from pillboy.games.base import GameView

logger = logging.getLogger(__name__)


class GameLoadError(Exception):
    pass


def load_game(manifest: dict) -> int:
    """
        Exec a game payload's python source, find its GameView subclass, and
        register it in GAMES. Returns the new game's index in GAMES.
    """
    name = manifest.get("name") or "QR Game"
    source = manifest["data"]

    namespace = {"__name__": f"pillboy.games.qr_loaded"}
    try:
        exec(compile(source, f"<qr:{name}>", "exec"), namespace)
    except Exception as e:
        raise GameLoadError(f"Game code failed to load: {e}")

    view_cls = None
    for value in namespace.values():
        if isinstance(value, type) and issubclass(value, GameView) and value is not GameView:
            view_cls = value
            break
    if view_cls is None:
        raise GameLoadError("No GameView subclass found in game code")

    if not hasattr(view_cls, "CONTROLS"):
        view_cls.CONTROLS = []

    entry = GameEntry(display_name=name, View_cls=view_cls)

    # Re-scanning a same-named game replaces the old version
    for i, existing in enumerate(GAMES):
        if existing.display_name == name:
            GAMES[i] = entry
            logger.info(f"Replaced QR-loaded game: {name}")
            return i

    GAMES.append(entry)
    logger.info(f"Loaded new QR game: {name}")
    return len(GAMES) - 1
