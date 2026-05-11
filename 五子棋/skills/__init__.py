"""招式系统 —— 10个主动技能定义与注册表"""

from .base import Skill, SkillType
from .definitions import (
    ExtraStone,
    CloneStone,
    DoubleMove,
    RemoveEnemy,
    ConvertStone,
    BlockPosition,
    SkipOpponent,
    ShiftOwnStone,
    SwapStones,
    RetractMove,
    ALL_SKILLS,
    random_skill,
)

__all__ = [
    "Skill", "SkillType",
    "ExtraStone", "CloneStone", "DoubleMove",
    "RemoveEnemy", "ConvertStone", "BlockPosition", "SkipOpponent",
    "ShiftOwnStone", "SwapStones", "RetractMove",
    "ALL_SKILLS", "random_skill",
]
