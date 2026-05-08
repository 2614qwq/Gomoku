"""万宁五子棋招式实现

主动招式: 玩家点击按钮触发
被动招式: 满足条件时自动触发

所有招式遵循"平衡弱化"原则: 数值压低，以正常五子棋对局逻辑为主。
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import random

from ..core.constants import BOARD_SIZE, BLACK, WHITE, EMPTY
from ..core.models import SkillResult, Position
from .base import Skill, SkillType

if TYPE_CHECKING:
    from ..core.models import Board, Player


# ============================================================================
# 主动招式（3个）
# ============================================================================

class WanningFormation(Skill):
    """万宁阵法：第5回合后可用，每局限一次，落子前在指定空位额外生成1子"""

    def __init__(self):
        super().__init__()
        self._used = False

    @property
    def skill_name(self): return "万宁阵法"

    @property
    def description(self): return "第5回合后可用，每局限一次，落子前在指定空位额外生成1子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count >= 5 and not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        if target is None or not board.is_empty(target.x, target.y):
            return SkillResult(message="万宁阵法：需要选择一个空位放置额外棋子")
        board.place(target.x, target.y, owner.color, is_skill=True)
        self._used = True
        return SkillResult(
            extra_stones=[target],
            message=f"万宁阵法发动！在({target.x},{target.y})额外生成1子"
        )


class BloodPrisonFormation(Skill):
    """血狱影杀阵：每回合可尝试一次，10%概率在上一落子相邻格生成1子"""

    def __init__(self):
        super().__init__()
        self._last_attempted_turn = -1

    @property
    def skill_name(self): return "血狱影杀阵"

    @property
    def description(self): return "落子前使用，每回合一次，10%概率在上一落子相邻格生成1子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return turn_count != self._last_attempted_turn

    def activate(self, owner, opponent, board, turn_count, target=None):
        self._last_attempted_turn = turn_count
        if random.random() > 0.1:
            return SkillResult(message="血狱影杀阵触发失败（90%概率未命中）")
        if target is None:
            empty_positions = board.get_empty_positions()
        else:
            empty_positions = board.get_adjacent_empty(target.x, target.y)
        if not empty_positions:
            return SkillResult(message="血狱影杀阵：无可用相邻空位")
        pos = random.choice(empty_positions)
        board.place(pos.x, pos.y, owner.color, is_skill=True)
        return SkillResult(
            extra_stones=[pos],
            message="血狱影杀阵发动！相邻1格生成1子"
        )


class FourDirectionsFormation(Skill):
    """四方阵：每局限一次，落子前删除场上随机棋子"""

    def __init__(self):
        super().__init__()
        self._used = False

    @property
    def skill_name(self): return "四方阵"

    @property
    def description(self): return "每局限一次，落子前删除场上随机1颗棋子"

    @property
    def skill_type(self): return SkillType.ACTIVE

    def can_activate(self, owner, board, turn_count):
        return not self._used

    def activate(self, owner, opponent, board, turn_count, target=None):
        all_stones = [Position(x, y) for y in range(BOARD_SIZE) for x in range(BOARD_SIZE)
                      if board.get(x, y) != EMPTY]
        if not all_stones:
            return SkillResult(message="四方阵：场上无棋子可删除")
        pos = random.choice(all_stones)
        removed_color = board.get(pos.x, pos.y)
        board.remove(pos.x, pos.y)
        self._used = True
        return SkillResult(
            removed_stones=[pos],
            message=f"四方阵发动！删除了({pos.x},{pos.y})的{removed_color}棋子"
        )


# ============================================================================
# 被动招式（7个）
# ============================================================================

class ReturnOriginFormation(Skill):
    """归元阵：自身连成4子时，额外生成1颗挡子"""

    @property
    def skill_name(self): return "归元阵"

    @property
    def description(self): return "被动：己方连成4子时自动生成1颗防守棋子"

    @property
    def skill_type(self): return SkillType.PASSIVE

    def on_own_move(self, owner, opponent, board, move_pos, turn_count):
        lines = board.find_lines(owner.color, 4)
        if not lines:
            return SkillResult()
        empty_positions = board.get_empty_positions()
        if not empty_positions:
            return SkillResult()
        pos = random.choice(empty_positions)
        board.place(pos.x, pos.y, owner.color, is_skill=True)
        return SkillResult(
            extra_stones=[pos],
            message="归元阵发动！连成4子，自动生成1颗防守棋子"
        )


class FiveThunderFormation(Skill):
    """五雷阵：对手释放技能后，随机清除对方1颗技能生成子"""

    @property
    def skill_name(self): return "五雷阵"

    @property
    def description(self): return "被动：对手释放招式后随机清除其1颗技能生成子"

    @property
    def skill_type(self): return SkillType.PASSIVE

    def on_opponent_skill(self, owner, opponent, board, turn_count):
        removed = board.remove_random_skill_stone_of(opponent.color)
        if removed is None:
            return SkillResult(message="五雷阵：对方无技能生成子可清除")
        return SkillResult(
            removed_stones=[removed],
            message=f"五雷阵发动！清除了对方的1颗技能生成子"
        )


class EightTrigramsFormation(Skill):
    """八卦阵：每5回合有概率转换对方1颗边角子"""

    @property
    def skill_name(self): return "八卦阵"

    @property
    def description(self): return "被动：每5回合有概率转换对方1颗边角棋子"

    @property
    def skill_type(self): return SkillType.PASSIVE

    def on_turn_end(self, owner, opponent, board, turn_count):
        if turn_count <= 0 or turn_count % 5 != 0:
            return SkillResult()
        if random.random() > 0.4:
            return SkillResult(message="八卦阵：本次未触发")
        opponent_edge = [Position(x, y) for y in range(BOARD_SIZE) for x in range(BOARD_SIZE)
                         if board.get(x, y) == opponent.color
                         and (x <= 1 or x >= BOARD_SIZE - 2 or y <= 1 or y >= BOARD_SIZE - 2)]
        if not opponent_edge:
            return SkillResult(message="八卦阵：对方无边角棋子")
        pos = random.choice(opponent_edge)
        board.remove(pos.x, pos.y)
        board.place(pos.x, pos.y, owner.color, is_skill=True)
        return SkillResult(
            message=f"八卦阵发动！转换了对方({pos.x},{pos.y})的棋子"
        )


class DragonTrapFormation(Skill):
    """困龙阵：对手连续同一直线落子时，随机封锁1个空位"""

    def __init__(self):
        super().__init__()
        self._opponent_last_pos: Optional[Position] = None

    @property
    def opponent_last_pos(self) -> Optional[Position]:
        """供 Agent 查询对方上一步落子位置"""
        return self._opponent_last_pos

    @property
    def skill_name(self): return "困龙阵"

    @property
    def description(self): return "被动：对手连续同一直线落子时随机封锁1个空位"

    @property
    def skill_type(self): return SkillType.PASSIVE

    def on_opponent_move(self, owner, opponent, board, move_pos, turn_count):
        last = self._opponent_last_pos
        self._opponent_last_pos = move_pos
        if last is None:
            return SkillResult()
        if not board.is_same_line(last, move_pos):
            return SkillResult()
        direction = board.get_line_direction(last, move_pos)
        if direction is None:
            return SkillResult()
        candidates = board.get_empty_on_line(move_pos, direction)
        if not candidates:
            return SkillResult()
        pos = random.choice(candidates)
        board.block(pos.x, pos.y)
        return SkillResult(
            blocked_positions=[pos],
            message=f"困龙阵发动！封锁了({pos.x},{pos.y})空位"
        )


class ExtinctionFormation(Skill):
    """绝户阵：对方技能生成子上限3颗"""

    @property
    def skill_name(self): return "绝户阵"

    @property
    def description(self): return "被动：对方场上最多保留3颗技能生成子"

    @property
    def skill_type(self): return SkillType.PASSIVE

    def on_opponent_move(self, owner, opponent, board, move_pos, turn_count):
        return self._enforce_limit(owner, opponent, board)

    def on_opponent_skill(self, owner, opponent, board, turn_count):
        return self._enforce_limit(owner, opponent, board)

    def _enforce_limit(self, owner, opponent, board):
        over = board.count_skill_stones_of(opponent.color) - 3
        if over <= 0:
            return SkillResult()
        removed_list = []
        for _ in range(over):
            removed = board.remove_random_skill_stone_of(opponent.color)
            if removed:
                removed_list.append(removed)
        if removed_list:
            return SkillResult(
                removed_stones=removed_list,
                message=f"绝户阵发动！对方技能生成子超出上限，清除了{len(removed_list)}颗"
            )
        return SkillResult()


class EnemyFirstStrike(Skill):
    """克敌先机：对手连成4子时，随机补1颗卡位子"""

    @property
    def skill_name(self): return "克敌先机"

    @property
    def description(self): return "被动：对手连成4子时自动补1颗防守棋子"

    @property
    def skill_type(self): return SkillType.PASSIVE

    def on_opponent_move(self, owner, opponent, board, move_pos, turn_count):
        lines = board.find_lines(opponent.color, 4)
        if not lines:
            return SkillResult()
        candidates = []
        for line in lines:
            for pos in line:
                for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
                    head = Position(line[-1].x + dx, line[-1].y + dy)
                    tail = Position(line[0].x - dx, line[0].y - dy)
                    for p in [head, tail]:
                        if p.is_valid() and board.is_empty(p.x, p.y):
                            candidates.append(p)
        if not candidates:
            candidates = board.get_empty_positions()
        if not candidates:
            return SkillResult()
        pos = random.choice(candidates)
        board.place(pos.x, pos.y, owner.color, is_skill=True)
        return SkillResult(
            extra_stones=[pos],
            message="克敌先机发动！对手快赢了，自动补1颗卡位子"
        )


class PlumBlossomFormation(Skill):
    """梅花阵：每4回合生成1颗花苞（仅格挡1次）"""

    def __init__(self):
        super().__init__()
        self._bud_position: Optional[Position] = None

    @property
    def bud_position(self) -> Optional[Position]:
        """供 Agent 查询当前花苞位置"""
        return self._bud_position

    @property
    def skill_name(self): return "梅花阵"

    @property
    def description(self): return "被动：每4回合生成1颗花苞，可格挡对方1次落子"

    @property
    def skill_type(self): return SkillType.PASSIVE

    def on_turn_end(self, owner, opponent, board, turn_count):
        if turn_count <= 0 or turn_count % 4 != 0:
            return SkillResult()

        # 每4回合清除旧花苞，生成新花苞
        if self._bud_position:
            board.unblock(self._bud_position.x, self._bud_position.y)
            self._bud_position = None

        empty_positions = [p for p in board.get_empty_positions()
                          if not board.is_blocked(p.x, p.y)]
        if not empty_positions:
            return SkillResult()
        self._bud_position = random.choice(empty_positions)
        board.block(self._bud_position.x, self._bud_position.y)
        return SkillResult(
            blocked_positions=[self._bud_position],
            message=f"梅花阵：生成了1颗花苞在({self._bud_position.x},{self._bud_position.y})，将格挡对方1次落子"
        )

    def on_opponent_move(self, owner, opponent, board, move_pos, turn_count):
        if not self._bud_position:
            return SkillResult()
        if move_pos.x == self._bud_position.x and move_pos.y == self._bud_position.y:
            # 对手踩中花苞——在控制器中已通过 is_empty 拦截，此处兜底清理
            board.unblock(self._bud_position.x, self._bud_position.y)
            self._bud_position = None
            return SkillResult(message="梅花阵：花苞格挡了对方落子！")
        return SkillResult()


# ============================================================================
# 招式注册表
# ============================================================================

ALL_SKILLS: list[type[Skill]] = [
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
]


def random_skill() -> Skill:
    """随机抽取一个招式实例"""
    cls = random.choice(ALL_SKILLS)
    return cls()
