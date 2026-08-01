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
    #
    # Games suffixed "1" are ports of the 2023 PillBoy card (see
    # ../../../PillBoy2023-sdcard); "2" is the version written for PillBoy3000.
    from pillboy.games.bounce import BounceGameView
    from pillboy.games.grubs import GrubsGameView
    from pillboy.games.snake import SnakeGameView
    from pillboy.games.snek import SnekGameView
    from pillboy.games.snek1 import SnekOneGameView
    from pillboy.games.starfighter import StarFighterGameView
    from pillboy.games.starsaver import StarSaverGameView
    from pillboy.games.sudoku import SudokuGameView
    from pillboy.games.tetris import TetrisGameView
    from pillboy.games.warpsnek import WarpSnekGameView

    return [
        GameEntry(display_name="Star Fighter", View_cls=StarFighterGameView,
                  icon_name=FontAwesomeIconConstants.JET_FIGHTER),
        GameEntry(display_name="Star Saver", View_cls=StarSaverGameView,
                  icon_name=FontAwesomeIconConstants.ROCKET),
        GameEntry(display_name="Tetris", View_cls=TetrisGameView,
                  icon_name=FontAwesomeIconConstants.CUBES),
        GameEntry(display_name="Snake", View_cls=SnakeGameView,
                  icon_name=FontAwesomeIconConstants.STAFF_SNAKE),
        GameEntry(display_name="Snek 1", View_cls=SnekOneGameView,
                  icon_name=FontAwesomeIconConstants.SPINNER),
        GameEntry(display_name="Snek 2", View_cls=SnekGameView,
                  icon_name=FontAwesomeIconConstants.CIRCLE_NOTCH),
        GameEntry(display_name="Warp Snek", View_cls=WarpSnekGameView,
                  icon_name=FontAwesomeIconConstants.SLASH),
        GameEntry(display_name="Grubs", View_cls=GrubsGameView,
                  icon_name=FontAwesomeIconConstants.BUG),
        GameEntry(display_name="Sudoku", View_cls=SudokuGameView,
                  icon_name=FontAwesomeIconConstants.BORDER_ALL),
        GameEntry(display_name="Bounce", View_cls=BounceGameView,
                  icon_name=FontAwesomeIconConstants.CIRCLE),
    ]


GAMES: list[GameEntry] = _load_games()
