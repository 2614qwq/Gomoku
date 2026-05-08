"""核心游戏模块 —— 常量、数据模型、游戏控制器"""

from .constants import (
    BOARD_SIZE, CELL_SIZE, MARGIN, STONE_RADIUS,
    BOARD_BG, LINE_COLOR, TEXT_COLOR,
    BLACK, WHITE, EMPTY, STAR_POINTS,
    DIRECTIONS, ADJACENT_4, DIAGONAL_4, ALL_8,
    WINDOW_WIDTH, WINDOW_HEIGHT,
)
from .models import Board, Player, Position, SkillResult
from .controller import GameController, GameState

__all__ = [
    "Board", "Player", "Position", "SkillResult",
    "GameController", "GameState",
    "BOARD_SIZE", "CELL_SIZE", "MARGIN", "STONE_RADIUS",
    "BOARD_BG", "LINE_COLOR", "TEXT_COLOR",
    "BLACK", "WHITE", "EMPTY", "STAR_POINTS",
    "WINDOW_WIDTH", "WINDOW_HEIGHT",
]
