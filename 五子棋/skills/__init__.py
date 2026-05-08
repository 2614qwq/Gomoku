"""招式系统 —— 万宁五子棋招式定义与注册表"""

from .base import Skill, SkillType
from .definitions import (
    WanningFormation,
    ReturnOriginFormation,
    FiveThunderFormation,
    EightTrigramsFormation,
    BloodPrisonFormation,
    FourDirectionsFormation,
    DragonTrapFormation,
    ExtinctionFormation,
    EnemyFirstStrike,
    PlumBlossomFormation,
    ALL_SKILLS,
    random_skill,
)

__all__ = [
    "Skill", "SkillType",
    "WanningFormation", "ReturnOriginFormation", "FiveThunderFormation",
    "EightTrigramsFormation", "BloodPrisonFormation", "FourDirectionsFormation",
    "DragonTrapFormation", "ExtinctionFormation", "EnemyFirstStrike",
    "PlumBlossomFormation",
    "ALL_SKILLS", "random_skill",
]
