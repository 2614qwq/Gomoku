"""招式基类与枚举定义"""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

from ..core.models import SkillResult, Position

if TYPE_CHECKING:
    from ..core.models import Board, Player


class SkillType(Enum):
    ACTIVE = auto()     # 主动：按钮触发
    PASSIVE = auto()    # 被动：条件自动触发


class Skill(ABC):
    """招式抽象基类"""

    @property
    @abstractmethod
    def skill_name(self) -> str:
        """招式名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """招式描述"""
        ...

    @property
    @abstractmethod
    def skill_type(self) -> SkillType:
        """主动 / 被动"""
        ...

    # ---- 主动招式接口 ----

    def can_activate(self, owner: Player, board: Board, turn_count: int) -> bool:
        """主动招式：检查可否激活（默认不可）"""
        return False

    def activate(self, owner: Player, opponent: Player, board: Board,
                 turn_count: int, target: Optional[Position] = None) -> SkillResult:
        """主动招式：执行激活，返回 SkillResult"""
        return SkillResult()

    # ---- 被动招式接口 ----

    def on_own_move(self, owner: Player, opponent: Player, board: Board,
                    move_pos: Position, turn_count: int) -> SkillResult:
        """己方落子后触发"""
        return SkillResult()

    def on_opponent_move(self, owner: Player, opponent: Player, board: Board,
                         move_pos: Position, turn_count: int) -> SkillResult:
        """对方落子后触发"""
        return SkillResult()

    def on_opponent_skill(self, owner: Player, opponent: Player, board: Board,
                          turn_count: int) -> SkillResult:
        """对方释放招式后触发"""
        return SkillResult()

    def on_turn_end(self, owner: Player, opponent: Player, board: Board,
                    turn_count: int) -> SkillResult:
        """回合结束时触发（用于周期性被动效果）"""
        return SkillResult()
