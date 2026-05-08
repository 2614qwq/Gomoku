"""游戏控制器 —— 管理游戏状态、流程、招式触发

职责：
  - 棋盘状态管理
  - 回合流转
  - 招式分配与触发调度
  - 游戏结束判定
"""
from __future__ import annotations
from enum import Enum, auto
from typing import Optional, Callable
import random

from .constants import BLACK, WHITE, EMPTY
from .models import Board, Player, Position, SkillResult
from ..skills import Skill, SkillType, random_skill, WanningFormation


class GameState(Enum):
    NORMAL = auto()            # 正常落子
    SKILL_TARGETING = auto()   # 等待技能目标位置
    GAME_OVER = auto()         # 游戏结束


class GameController:
    """五子棋游戏控制器

    Usage:
        ctrl = GameController()
        ctrl.on_skill_activate = lambda: ...    # 设置回调
        ctrl.on_state_changed = lambda: ...     # 状态变更回调
        ctrl.start_new_game()
        ctrl.handle_click(x, y)                 # 处理棋盘点击
    """

    def __init__(self):
        self.board = Board()
        self.black_player = Player(BLACK, "黑棋")
        self.white_player = Player(WHITE, "白棋")

        self._turn = 0          # 0=黑, 1=白
        self._turn_count = 0    # 总回合数
        self._state = GameState.GAME_OVER
        self._pending_skill: Optional[Skill] = None  # 等待选择目标的主动招式
        self._last_move_pos: Optional[Position] = None  # 上一步落子位置
        self._game_mode = 0     # 0=双人, 1=人机(黑), 2=人机(白), 3=AIvsAI
        self._ai_enabled = False
        self._orchestrator = None  # 延迟加载

        # 回调
        self.on_state_changed: Optional[Callable] = None
        self.on_skill_triggered: Optional[Callable[[str, str], None]] = None
        self.on_game_over: Optional[Callable[[str], None]] = None
        self.on_ai_analysis: Optional[Callable[[dict], None]] = None  # AI 分析结果回调

    # ================== 属性 ==================

    @property
    def turn(self) -> int:
        return self._turn

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def game_mode(self) -> int:
        return self._game_mode

    @game_mode.setter
    def game_mode(self, value: int):
        self._game_mode = value

    @property
    def current_player(self) -> Player:
        return self.black_player if self._turn == 0 else self.white_player

    @property
    def opponent_player(self) -> Player:
        return self.white_player if self._turn == 0 else self.black_player

    def is_game_over(self) -> bool:
        return self._state == GameState.GAME_OVER

    def is_skill_targeting(self) -> bool:
        return self._state == GameState.SKILL_TARGETING

    # ================== AI 接口 ==================

    def enable_ai(self):
        """启用多智能体系统"""
        self._ai_enabled = True
        if self._orchestrator is None:
            from agent import MultiAgentOrchestrator
            self._orchestrator = MultiAgentOrchestrator()

    def disable_ai(self):
        self._ai_enabled = False

    @property
    def ai_enabled(self) -> bool:
        return self._ai_enabled

    @property
    def orchestrator(self):
        return self._orchestrator

    def trigger_ai_move(self) -> Optional[dict]:
        """触发 AI 落子。返回 {"result": ..., "analysis": ...} 或 None。

        在 game_window 的后台线程中调用。
        analysis 数据由 UI 线程处理（避免 tkinter 线程安全问题）。
        """
        if not self._ai_enabled or self._orchestrator is None:
            return None
        if self._state == GameState.GAME_OVER:
            return None

        decision = self._orchestrator.analyze(self)
        x, y = decision.move

        analysis = {
            "move": decision.move,
            "reason": decision.reason,
            "summaries": decision.agent_summaries,
        }

        result = self.handle_click(x, y)
        return {"result": result, "analysis": analysis}

    def handle_human_question(self, question: str) -> dict:
        """处理人类反问，返回 AI 的重新分析结果"""
        if not self._ai_enabled or self._orchestrator is None:
            return {"error": "AI 未启用"}
        decision = self._orchestrator.analyze(self, human_question=question)
        return {
            "move": decision.move,
            "reason": decision.reason,
            "summaries": decision.agent_summaries,
        }

    def request_ai_hint(self) -> Optional[dict]:
        """为当前人类玩家请求 AI 提示（不实际落子）

        由人类玩家在技能窗口点击"AI提示"按钮触发。
        多智能体分析当前局面后返回建议，最终决策由人类做出。

        Returns:
            {"move": (x,y), "reason": str, "summaries": dict} 或 None
        """
        if not self._ai_enabled or self._orchestrator is None:
            return None
        if self._state == GameState.GAME_OVER:
            return None
        decision = self._orchestrator.analyze(self)
        return {
            "move": decision.move,
            "reason": decision.reason,
            "summaries": decision.agent_summaries,
        }

    # ================== 游戏流程 ==================

    def start_new_game(self):
        """开始新游戏：重置棋盘、随机分配招式"""
        self.board.reset()
        self._turn = 0
        self._turn_count = 0
        self._state = GameState.NORMAL
        self._pending_skill = None
        self._last_move_pos = None

        # 随机分配招式
        self.black_player.skill = random_skill()
        self.white_player.skill = random_skill()
        # 确保双方招式不同
        while self.white_player.skill.__class__ == self.black_player.skill.__class__:
            self.white_player.skill = random_skill()

        self._notify_state_changed()

    def handle_click(self, x: int, y: int) -> Optional[str]:
        """处理棋盘点击

        Returns:
            获胜消息（游戏结束），否则 None
        """
        if self._state == GameState.GAME_OVER:
            return None

        if self._state == GameState.SKILL_TARGETING:
            return self._handle_skill_target(x, y)

        return self._handle_normal_move(x, y)

    def activate_skill(self) -> Optional[str]:
        """激活当前玩家的主动招式（由技能窗口按钮触发）

        Returns:
            错误消息或 None
        """
        if self._state == GameState.GAME_OVER:
            return "游戏已结束"

        player = self.current_player
        skill = player.skill
        if skill is None or skill.skill_type != SkillType.ACTIVE:
            return "没有可用的主动招式"

        if not skill.can_activate(player, self.board, self._turn_count):
            return "招式尚未冷却完毕"

        # 需要选择目标的招式（如万宁阵法）进入瞄准模式
        if self._needs_target(skill):
            self._state = GameState.SKILL_TARGETING
            self._pending_skill = skill
            self._notify_state_changed()
            return None

        # 不需要目标的招式直接执行，传入上一步落子位置作为锚点
        result = skill.activate(player, self.opponent_player, self.board,
                               self._turn_count, target=self._last_move_pos)
        self._apply_result(result, self.current_player)

        # 触发对手被动：对方释放技能后
        self._trigger_reactions_to_skill()

        self._notify_state_changed()
        return None

    def _trigger_reactions_to_skill(self):
        """触发对手对技能释放的反应（五雷阵、绝户阵等）"""
        opponent = self.opponent_player
        player = self.current_player
        if opponent.skill:
            reaction = opponent.skill.on_opponent_skill(opponent, player, self.board, self._turn_count)
            self._apply_result(reaction, opponent)
        # 绝户阵限制
        if opponent.skill:
            limit_result = self._check_extinction_limit(opponent, player)
            self._apply_result(limit_result, opponent)

    # ================== 内部处理 ==================

    def _handle_normal_move(self, x: int, y: int) -> Optional[str]:
        """处理正常落子"""
        player = self.current_player
        opponent = self.opponent_player

        if not self.board.is_empty(x, y):
            return None

        # 执行落子
        self.board.place(x, y, player.color, is_skill=False)
        self._turn_count += 1
        move_pos = Position(x, y)
        self._last_move_pos = move_pos

        # 检查胜负
        if self.board.check_win(player.color):
            self._state = GameState.GAME_OVER
            self._notify_state_changed()
            msg = f"{player.name}获胜！🎉"
            if self.on_game_over:
                self.on_game_over(msg)
            return msg

        if self.board.is_full():
            self._state = GameState.GAME_OVER
            self._notify_state_changed()
            msg = "平局！🤝"
            if self.on_game_over:
                self.on_game_over(msg)
            return msg

        # 被动招式：己方落子后
        self._trigger_passive_on_own_move(player, opponent, move_pos)

        # 被动招式：对方落子后（以对手视角）
        self._trigger_passive_on_opponent_move(opponent, player, move_pos)

        # 被动招式：回合结束
        self._trigger_passive_on_turn_end(player, opponent)
        self._trigger_passive_on_turn_end(opponent, player)

        # 切换回合
        self._turn = 1 - self._turn
        self._notify_state_changed()

        # 重新检查胜负（被动招式可能改变了棋盘）
        if self.board.check_win(self.current_player.color):
            self._state = GameState.GAME_OVER
            self._notify_state_changed()
            msg = f"{self.current_player.name}获胜！🎉"
            if self.on_game_over:
                self.on_game_over(msg)
            return msg

        return None

    def _handle_skill_target(self, x: int, y: int) -> Optional[str]:
        """处理招式目标选择"""
        skill = self._pending_skill
        self._pending_skill = None
        self._state = GameState.NORMAL

        if skill is None:
            return None

        player = self.current_player
        opponent = self.opponent_player

        # 验证目标位置
        if not self.board.is_valid(x, y):
            self._notify_state_changed()
            return None

        target = Position(x, y)

        result = skill.activate(player, opponent, self.board, self._turn_count, target=target)
        self._apply_result(result, player)

        # 触发对手对技能释放的反应
        self._trigger_reactions_to_skill()

        self._notify_state_changed()
        return None

    def _trigger_passive_on_own_move(self, player: Player, opponent: Player, move_pos: Position):
        """触发己方落子后的被动招式"""
        if player.skill:
            result = player.skill.on_own_move(player, opponent, self.board, move_pos, self._turn_count)
            self._apply_result(result, player)
        # 绝户阵：对手回合后检查限制
        if opponent.skill:
            result = self._check_extinction_limit(opponent, player)
            self._apply_result(result, opponent)

    def _trigger_passive_on_opponent_move(self, player: Player, opponent: Player, move_pos: Position):
        """以 player 视角：对手落子后触发的被动"""
        if player.skill:
            result = player.skill.on_opponent_move(player, opponent, self.board, move_pos, self._turn_count)
            self._apply_result(result, player)

    def _trigger_passive_on_turn_end(self, player: Player, opponent: Player):
        """回合结束时触发的被动"""
        if player.skill:
            result = player.skill.on_turn_end(player, opponent, self.board, self._turn_count)
            self._apply_result(result, player)

    def _check_extinction_limit(self, owner: Player, opponent: Player) -> SkillResult:
        """绝户阵限制检查"""
        from ..skills import ExtinctionFormation
        if isinstance(owner.skill, ExtinctionFormation):
            over = self.board.count_skill_stones_of(opponent.color) - 3
            if over > 0:
                removed_list = []
                for _ in range(over):
                    removed = self.board.remove_random_skill_stone_of(opponent.color)
                    if removed:
                        removed_list.append(removed)
                if removed_list:
                    return SkillResult(
                        removed_stones=removed_list,
                        message=f"绝户阵发动！对方技能生成子超出上限，清除了{len(removed_list)}颗"
                    )
        return SkillResult()

    def _apply_result(self, result: SkillResult, triggering_player: Player):
        """应用招式结果并通知 UI"""
        if not result.message:
            return
        if self.on_skill_triggered:
            self.on_skill_triggered(triggering_player.name, result.message)

    def _needs_target(self, skill: Skill) -> bool:
        """判断招式是否需要选择目标位置（万宁阵法需要手动选位）"""
        return isinstance(skill, WanningFormation)

    def _notify_state_changed(self):
        if self.on_state_changed:
            self.on_state_changed()

    # ================== 招式面板数据 ==================

    def get_current_skill_info(self) -> dict:
        """获取当前玩家的招式信息（供技能窗口使用）"""
        player = self.current_player
        skill = player.skill
        can_use = False
        if skill and skill.skill_type == SkillType.ACTIVE:
            can_use = skill.can_activate(player, self.board, self._turn_count)
        return {
            'current_player': player,
            'opponent': self.opponent_player,
            'skill_active': can_use,
            'state': self._state,
        }
