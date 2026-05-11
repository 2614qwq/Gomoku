"""五子棋技能实现（10个主动技能）

全部为主动技能：每局限1次，必成功，在落子前使用。
技能使用后立即生效，然后继续正常落子，回合切换。

设计原则：
  - 每个技能条件清晰，Agent从game_report中直接读到是否"值得使用"
  - 效果"超自然"但不破坏五子棋基本规则（五连获胜）
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import random

from ..core.constants import BOARD_SIZE, BLACK, WHITE
from ..core.models import SkillResult, Position
from .base import Skill, SkillType

if TYPE_CHECKING:
    from ..core.models import Board, Player


# ============================================================================
# 技能1-3: 进攻档 —— 直接增强己方棋盘力量
# ============================================================================

class ExtraStone(Skill):
    """追加落子：在当前回合额外放置1子在任意空位"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "追加落子"

    @property
    def description(self): return "第5回合起可用，每局限1次，在任意空位额外放置1子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 5 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        if target is None or not board.is_empty(target.x, target.y):
            return SkillResult(message="追加落子：需要选择一个空位")
        board.place(target.x, target.y, owner.color)
        self._used = True
        return SkillResult(
            extra_stones=[target],
            message=f"追加落子：在{target}额外生成1子"
        )


class CloneStone(Skill):
    """复制己子：在己方1子的相邻4格空位中生成1颗同色子"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "复制己子"

    @property
    def description(self): return "第3回合起可用，每局限1次，选择己方1子在其相邻空位生成同色子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 3 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        if target is None:
            return SkillResult(message="复制己子：需要选择目标空位（必须是己方棋子相邻格）")
        if not board.is_empty(target.x, target.y):
            return SkillResult(message=f"复制己子：{target}不是空位")
        # 检查相邻格是否有己方棋子
        has_adjacent_own = False
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = target.x + dx, target.y + dy
            if board.is_valid(nx, ny) and board.get_color(nx, ny) == owner.color:
                has_adjacent_own = True
                break
        if not has_adjacent_own:
            return SkillResult(message=f"复制己子：{target}相邻4格内无己方棋子")
        board.place(target.x, target.y, owner.color)
        self._used = True
        return SkillResult(
            extra_stones=[target],
            message=f"复制己子：在{target}生成1子"
        )


class DoubleMove(Skill):
    """连打两子：本回合连续落下2子（而不是正常的1子）"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "连打两子"

    @property
    def description(self): return "第10回合起可用，每局限1次，本回合连续落下2子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 10 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        """连打两子：由调用方先后两次调用 place 落两个子。此处仅标记已使用。
        实际落子由 controller 在技能激活后额外调用一次 place。
        """
        self._used = True
        return SkillResult(
            message="连打两子：请连续选择两个落子位置"
        )


# ============================================================================
# 技能4-7: 控制档 —— 削弱或限制对手
# ============================================================================

class RemoveEnemy(Skill):
    """移除敌子：删除对手任意1颗棋子"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "移除敌子"

    @property
    def description(self): return "第3回合起可用，每局限1次，选择并移除对手1颗棋子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 3 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        if target is None:
            return SkillResult(message="移除敌子：需要选择对手1颗棋子作为目标")
        if not board.is_valid(target.x, target.y):
            return SkillResult(message=f"移除敌子：{target}坐标非法")
        if board.get_color(target.x, target.y) != opponent.color:
            return SkillResult(message=f"移除敌子：{target}不是对手棋子")
        board.remove(target.x, target.y)
        self._used = True
        return SkillResult(
            removed_stones=[target],
            message=f"移除敌子：删除了对手在{target}的棋子"
        )


class ConvertStone(Skill):
    """转化棋子：将对手1子变为己方颜色"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "转化棋子"

    @property
    def description(self): return "第8回合起可用，每局限1次，将对手1颗棋子变为己方颜色"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 8 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        if target is None:
            return SkillResult(message="转化棋子：需要选择对手1颗棋子")
        if not board.is_valid(target.x, target.y):
            return SkillResult(message=f"转化棋子：{target}坐标非法")
        if board.get_color(target.x, target.y) != opponent.color:
            return SkillResult(message=f"转化棋子：{target}不是对手棋子")
        # 移除对手子，再以己方颜色放回（保持位置）
        board.remove(target.x, target.y)
        board.place(target.x, target.y, owner.color)
        self._used = True
        return SkillResult(
            message=f"转化棋子：将对手在{target}的棋子变为己方"
        )


class BlockPosition(Skill):
    """封禁空位：标记1个空位，对手下1回合不能落此位"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "封禁空位"

    @property
    def description(self): return "第3回合起可用，每局限1次，封锁1空位（格挡对手1回合）"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 3 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        if target is None:
            return SkillResult(message="封禁空位：需要选择一个空位")
        if not board.is_valid(target.x, target.y):
            return SkillResult(message=f"封禁空位：{target}坐标非法")
        if not board.is_empty(target.x, target.y):
            return SkillResult(message=f"封禁空位：{target}不是空位")
        board.block(target.x, target.y)
        self._used = True
        return SkillResult(
            blocked_positions=[target],
            message=f"封禁空位：封锁{target}，对手下回合不可落此位"
        )


class SkipOpponent(Skill):
    """强制跳过：对手跳过下个回合"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "强制跳过"

    @property
    def description(self): return "第8回合起可用，每局限1次，对手跳过下个回合"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 8 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        """由 controller 处理：标记 skip_opponent_next_turn = True"""
        self._used = True
        return SkillResult(
            message="强制跳过：对手将跳过下个回合"
        )


# ============================================================================
# 技能8-10: 技巧档 —— 调整已有棋子
# ============================================================================

class ShiftOwnStone(Skill):
    """移位己子：将己方1子移动到相邻8格内的任意空位"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "移位己子"

    @property
    def description(self): return "第3回合起可用，每局限1次，将己方1子移动到相邻空位"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 3 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        """需要两个参数：source(己方棋子) 和 target(目标空位)"""
        # target 是第一参数（新位置）
        if target is None:
            return SkillResult(message="移位己子：需要选择目标空位（相邻8格内的己方棋子会自动识别）")

        if not board.is_empty(target.x, target.y):
            return SkillResult(message=f"移位己子：{target}不是空位")

        # 在相邻8格中找己方棋子
        source = None
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            sx, sy = target.x + dx, target.y + dy
            if board.is_valid(sx, sy) and board.get_color(sx, sy) == owner.color:
                source = Position(sx, sy)
                break

        if source is None:
            return SkillResult(message=f"移位己子：{target}相邻8格内无己方棋子可移动")

        board.remove(source.x, source.y)
        board.place(target.x, target.y, owner.color)
        self._used = True
        return SkillResult(
            message=f"移位己子：将{source}的棋子移到{target}"
        )


class SwapStones(Skill):
    """交换棋子：交换己方1子与对手1子的位置"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "交换棋子"

    @property
    def description(self): return "第8回合起可用，每局限1次，交换己方1子与对手1子的位置"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 8 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        """target 是己方棋子位置；在相邻或附近搜索对手棋子交换"""
        if target is None:
            return SkillResult(message="交换棋子：需要选择己方1颗棋子")
        if not board.is_valid(target.x, target.y):
            return SkillResult(message=f"交换棋子：{target}坐标非法")
        if board.get_color(target.x, target.y) != owner.color:
            return SkillResult(message=f"交换棋子：{target}不是己方棋子")

        # 搜索附近的对手棋子（优先同方向上最近的）
        opponent_target = None
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nx, ny = target.x + dx, target.y + dy
            if board.is_valid(nx, ny) and board.get_color(nx, ny) == opponent.color:
                opponent_target = Position(nx, ny)
                break

        if opponent_target is None:
            return SkillResult(message=f"交换棋子：{target}相邻无对手棋子可交换")

        # 执行交换：移除→各自以对方颜色重新落子
        board.remove(target.x, target.y)
        board.remove(opponent_target.x, opponent_target.y)
        board.place(target.x, target.y, opponent.color)
        board.place(opponent_target.x, opponent_target.y, owner.color)
        self._used = True
        return SkillResult(
            message=f"交换棋子：交换了{target}(己)与{opponent_target}(敌)的位置"
        )


class RetractMove(Skill):
    """回溯落子：撤销自己上一步落子，重新选择落子位置"""

    def __init__(self):
        self._used = False

    @property
    def skill_name(self): return "回溯落子"

    @property
    def description(self): return "第5回合起可用，每局限1次，撤销自己上一步落子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 5 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        """target 是上一步自己的落子位置（由 controller 传入）"""
        if target is None:
            return SkillResult(message="回溯落子：需要指定上一步的落子位置")
        if not board.is_valid(target.x, target.y):
            return SkillResult(message=f"回溯落子：{target}坐标非法")
        if board.get_color(target.x, target.y) != owner.color:
            return SkillResult(message=f"回溯落子：{target}不是己方棋子，可能不是上一步")
        board.remove(target.x, target.y)
        self._used = True
        return SkillResult(
            removed_stones=[target],
            message=f"回溯落子：撤销了{target}的落子，请重新选择位置"
        )


# ============================================================================
# 招式注册表
# ============================================================================

ALL_SKILLS: list[type[Skill]] = [
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
]


def random_skill() -> Skill:
    """随机抽取一个招式实例"""
    cls = random.choice(ALL_SKILLS)
    return cls()
