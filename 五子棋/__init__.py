"""五子棋 —— 万宁招式版

目录结构:
    core/       - 核心游戏逻辑（常量、数据模型、控制器）
    skills/     - 招式系统（基类、10个招式实现、注册表）
    ui/         - 用户界面（招式面板、游戏主窗口）
"""

from .core import Board, Player, Position, SkillResult, GameController, GameState
from .core.constants import BOARD_SIZE, BLACK, WHITE, EMPTY
from .skills import Skill, SkillType, ALL_SKILLS, random_skill
from .ui import SkillWindow, GomokuGUI

__all__ = [
    "Board", "Player", "Position", "SkillResult",
    "GameController", "GameState",
    "Skill", "SkillType", "ALL_SKILLS", "random_skill",
    "SkillWindow", "GomokuGUI",
    "BOARD_SIZE", "BLACK", "WHITE", "EMPTY",
]
