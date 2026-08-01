from dataclasses import dataclass
from typing import Type


@dataclass
class GameEntry:
    """A single game as it appears in the main menu game picker."""
    display_name: str
    View_cls: Type


def _load_games() -> list[GameEntry]:
    # Import here (not at module top) so a broken game module fails at menu-build
    # time with a visible error screen instead of killing the whole app at import.
    from pillboy.games.bounce import BounceGameView
    from pillboy.games.tetris import TetrisGameView

    return [
        GameEntry(display_name="Tetris", View_cls=TetrisGameView),
        GameEntry(display_name="Bounce", View_cls=BounceGameView),
    ]


GAMES: list[GameEntry] = _load_games()
