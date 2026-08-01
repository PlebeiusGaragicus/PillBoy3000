from dataclasses import dataclass
from typing import Type

from pillboy.gui.components import FontAwesomeIconConstants


@dataclass
class GameEntry:
    """A single game as it appears in the main menu game picker."""
    display_name: str
    View_cls: Type
    icon_name: str = FontAwesomeIconConstants.GAMEPAD


def _load_games() -> list[GameEntry]:
    # Import here (not at module top) so a broken game module fails at menu-build
    # time with a visible error screen instead of killing the whole app at import.
    from pillboy.games.bounce import BounceGameView
    from pillboy.games.snake import SnakeGameView
    from pillboy.games.starfighter import StarFighterGameView
    from pillboy.games.sudoku import SudokuGameView
    from pillboy.games.tetris import TetrisGameView

    return [
        GameEntry(display_name="Star Fighter", View_cls=StarFighterGameView,
                  icon_name=FontAwesomeIconConstants.JET_FIGHTER),
        GameEntry(display_name="Tetris", View_cls=TetrisGameView,
                  icon_name=FontAwesomeIconConstants.CUBES),
        GameEntry(display_name="Snake", View_cls=SnakeGameView,
                  icon_name=FontAwesomeIconConstants.STAFF_SNAKE),
        GameEntry(display_name="Sudoku", View_cls=SudokuGameView,
                  icon_name=FontAwesomeIconConstants.BORDER_ALL),
        GameEntry(display_name="Bounce", View_cls=BounceGameView,
                  icon_name=FontAwesomeIconConstants.CIRCLE),
    ]


GAMES: list[GameEntry] = _load_games()
