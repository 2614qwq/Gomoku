"""游戏控制器 —— 管理游戏状态、流程、招式触发

职责：
  - 棋盘状态管理（int 网格）
  - 回合流转
  - 主动技能：分配、激活、执行
  - 游戏结束判定
"""

from __future__ import annotations
from enum import Enum, auto
from typing import Optional, Callable
import random

from .constants import BLACK, WHITE
from .models import Board, Player, Position, SkillResult
from agent.logger import get_logger

_log = get_logger("controller")
from ..skills import Skill, SkillType, random_skill


class GameState(Enum):
    NORMAL = auto()            # 正常落子
    SKILL_TARGETING = auto()   # 等待技能目标选择（需要选坐标的技能）
    GAME_OVER = auto()         # 游戏结束


class GameController:
    """五子棋游戏控制器

    Usage:
        ctrl = GameController()
        ctrl.on_state_changed = lambda: ...
        ctrl.start_new_game()
        ctrl.handle_click(x, y)
    """

    def __init__(self):
        self.board = Board()
        self.black_player = Player(BLACK, "黑棋")
        self.white_player = Player(WHITE, "白棋")

        self._turn = 0          # 0=黑, 1=白
        self._turn_count = 0    # 总回合数
        self._state = GameState.GAME_OVER
        self._pending_skill: Optional[Skill] = None  # 等待选择目标的主动技能
        self._pending_skill_args: Optional[dict] = None  # 技能所需的额外参数
        self._last_move_pos: Optional[Position] = None  # 上一步落子位置
        self._game_mode = 0     # 0=双人, 1=人机(黑), 2=人机(白), 3=AIvsAI
        self._ai_enabled = False
        self._orchestrator = None  # 延迟加载
        self._skip_next_opponent_turn = False  # 强制跳过对手回合
        self._double_move_active = False  # 连打两子激活中
        self._double_move_count = 0  # 连打两子已落子数
        self._own_last_move_pos: Optional[Position] = None  # 己方上一步（供回溯落子用）

        # 回调
        self.on_state_changed: Optional[Callable] = None
        self.on_skill_triggered: Optional[Callable[[str, str], None]] = None
        self.on_game_over: Optional[Callable[[str], None]] = None
        self.on_ai_analysis: Optional[Callable[[dict], None]] = None

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
        """触发 AI 落子。返回 {"result": ..., "analysis": ...} 或 None。"""
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

        if decision.activate_skill and result is None:
            skill_result = self._execute_ai_skill(decision.activate_skill)
            if skill_result:
                analysis["skill_result"] = skill_result

        return {"result": result, "analysis": analysis}

    def _execute_ai_skill(self, activate: dict) -> Optional[str]:
        """执行 AI 决定的技能激活"""
        player = self.current_player
        skill = player.skill
        if skill is None:
            return None
        if not skill.can_activate(player, self.board, self._turn_count):
            return None

        from ..五子棋.core.models import Position
        args = activate.get("args", {})
        target = None
        if "x" in args and "y" in args:
            target = Position(args["x"], args["y"])

        result = skill.activate(
            player, self.opponent_player, self.board,
            self._turn_count, target=target)

        if result and result.message:
            _log.info(f"AI 技能执行: {result.message}")
            self._apply_result(result, player)

        self._notify_state_changed()
        return result.message if result else None

    def handle_human_question(self, question: str) -> dict:
        """处理人类反问"""
        if not self._ai_enabled or self._orchestrator is None:
            return {"error": "AI 未启用"}
        decision = self._orchestrator.analyze(self, human_question=question)
        return {
            "move": decision.move,
            "reason": decision.reason,
            "summaries": decision.agent_summaries,
        }

    def request_ai_hint(self) -> Optional[dict]:
        """为人类玩家请求 AI 提示（不实际落子）"""
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
        """开始新游戏"""
        self.board.reset()
        self._turn = 0
        self._turn_count = 0
        self._state = GameState.NORMAL
        self._pending_skill = None
        self._pending_skill_args = None
        self._last_move_pos = None
        self._own_last_move_pos = None
        self._skip_next_opponent_turn = False
        self._double_move_active = False
        self._double_move_count = 0

        # 随机分配技能（双方不同）
        self.black_player.skill = random_skill()
        self.white_player.skill = random_skill()
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
        """激活当前玩家的主动技能（由技能面板按钮触发）

        Returns:
            错误消息或 None
        """
        if self._state == GameState.GAME_OVER:
            return "游戏已结束"

        player = self.current_player
        skill = player.skill
        if skill is None:
            return "没有可用的招式"

        if not skill.can_activate(player, self.board, self._turn_count):
            return "招式不可用（已使用或回合不足）"

        name = skill.skill_name

        # 需要坐标参数的技能 → 进入瞄准模式
        if name in ("追加落子", "移除敌子", "转化棋子", "封禁空位",
                     "复制己子", "移位己子", "交换棋子"):
            self._state = GameState.SKILL_TARGETING
            self._pending_skill = skill
            self._notify_state_changed()
            return None

        # 无参数技能 → 直接执行
        result = skill.activate(player, self.opponent_player, self.board,
                                self._turn_count)
        self._apply_result(result, player)

        # 连打两子：标记激活
        if name == "连打两子":
            self._double_move_active = True
            self._double_move_count = 0

        # 强制跳过：标记跳过
        if name == "强制跳过":
            self._skip_next_opponent_turn = True

        # 回溯落子：已撤销上一步，需要重新落子
        if name == "回溯落子":
            if self._own_last_move_pos:
                result = skill.activate(player, self.opponent_player, self.board,
                                        self._turn_count, target=self._own_last_move_pos)
                self._apply_result(result, player)
                # 回合不切换，玩家重新选位落子
                self._notify_state_changed()
                return None

        self._notify_state_changed()
        return None

    # ================== 内部处理 ==================

    def _handle_normal_move(self, x: int, y: int) -> Optional[str]:
        """处理正常落子"""
        player = self.current_player

        if not self.board.is_empty(x, y):
            return None

        # 落子（place 返回新序号）
        seq = self.board.place(x, y, player.color)
        if seq == 0:
            return None  # 落子失败

        self._turn_count += 1
        move_pos = Position(x, y)
        self._last_move_pos = move_pos
        self._own_last_move_pos = move_pos

        # 检查胜负
        if self.board.check_win(player.color):
            self._state = GameState.GAME_OVER
            self._notify_state_changed()
            msg = f"{player.name}获胜！"
            if self.on_game_over:
                self.on_game_over(msg)
            return msg

        if self.board.is_full():
            self._state = GameState.GAME_OVER
            self._notify_state_changed()
            msg = "平局！"
            if self.on_game_over:
                self.on_game_over(msg)
            return msg

        # 连打两子处理
        if self._double_move_active:
            self._double_move_count += 1
            if self._double_move_count < 2:
                # 还需要再落1子
                self._notify_state_changed()
                return None
            else:
                # 落完2子，恢复正常
                self._double_move_active = False
                self._double_move_count = 0

        # 回合切换
        if self._skip_next_opponent_turn:
            self._skip_next_opponent_turn = False
            # 对手跳过，本方再走一轮
        else:
            self._turn = 1 - self._turn

        self._notify_state_changed()
        return None

    def _handle_skill_target(self, x: int, y: int) -> Optional[str]:
        """处理技能目标选择（进入 SKILL_TARGETING 状态后点击棋盘）"""
        skill = self._pending_skill
        self._pending_skill = None
        self._state = GameState.NORMAL

        if skill is None:
            return None

        player = self.current_player
        opponent = self.opponent_player

        target = Position(x, y)

        result = skill.activate(player, opponent, self.board,
                                self._turn_count, target=target)
        self._apply_result(result, player)

        # 连打两子标记
        if skill.skill_name == "连打两子":
            self._double_move_active = True
            self._double_move_count = 0

        # 强制跳过标记
        if skill.skill_name == "强制跳过":
            self._skip_next_opponent_turn = True

        self._notify_state_changed()
        return None

    def _apply_result(self, result: SkillResult, triggering_player: Player):
        """应用技能结果并通知 UI"""
        if not result.message:
            return
        if self.on_skill_triggered:
            self.on_skill_triggered(triggering_player.name, result.message)

    def _needs_target(self, skill: Skill) -> bool:
        """判断技能是否需要选择目标坐标"""
        return skill.skill_name in (
            "追加落子", "移除敌子", "转化棋子", "封禁空位",
            "复制己子", "移位己子", "交换棋子",
        )

    def _notify_state_changed(self):
        if self.on_state_changed:
            self.on_state_changed()

    # ================== 技能面板数据 ==================

    def get_current_skill_info(self) -> dict:
        """获取当前玩家的技能信息（供技能窗口使用）"""
        player = self.current_player
        skill = player.skill
        can_use = False
        if skill:
            can_use = skill.can_activate(player, self.board, self._turn_count)
        return {
            'current_player': player,
            'opponent': self.opponent_player,
            'skill_name': skill.skill_name if skill else "无",
            'skill_description': skill.description if skill else "",
            'skill_active': can_use,
            'state': self._state,
        }
