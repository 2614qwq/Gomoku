"""MultiAgentOrchestrator —— LangGraph StateGraph 编排器

  - phase_check → [Send("tactical") || Send("defense")]  — LangGraph 原生 fan-out
  - post_analysis 作为 join 节点，汇总并行结果
  - 全流程由 AI 决策 + 算法预检兜底（强制必胜/必堵）
  - tactical 与 defense 共识时跳过 chief
"""
from __future__ import annotations
import sys
import os
from typing import Optional, Union

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send

from .state import MultiAgentState
from .protocol import FinalDecision
from ..logger import get_logger

_log = get_logger("orchestrator")

# 算法模块
from ..algorithm import (
    find_immediate_win, find_must_block, scan_threats,
    find_double_threat_moves, find_existing_live3_blocks, get_best_move,
)


def _explain_invalid(x: int, y: int, board) -> str:
    """解释为什么 (x,y) 不可落子"""
    if not (0 <= x < 15 and 0 <= y < 15):
        return "超出棋盘范围(0-14)"
    v = board.get(x, y)
    if v != 0:
        ch = board.get_color(x, y)
        return f"已被棋子占据({ch})"
    if board.is_blocked(x, y):
        return "是封锁位(*)"
    return "不可用"


from ..llm_client import LLMClient
from ..agents.tactical_analyst import TacticalAnalyst
from ..agents.defense_specialist import DefenseSpecialist
from ..agents.skill_officer import SkillOfficer
from ..agents.chief_strategist import ChiefStrategist
from ..game_info.extractor import GameInfoExtractor
from ..memory.sliding_memory import SlidingMemory
from ..speed.speed_controller import SpeedController
from ..skill_tools import get_skill_tool

# RAG 模块（可选，首次索引后生效）
_rag_tools = None
_rag_executor = None


def _init_rag():
    """懒加载 RAG tools 和 executor"""
    global _rag_tools, _rag_executor
    if _rag_tools is None:
        try:
            from rag import get_tools
            registry = get_tools()
            _rag_tools = registry.get_schemas()
            _rag_executor = registry.execute
            _log.info(f"RAG 已加载: {registry.tool_names}")
        except Exception as e:
            _log.warning(f"RAG 加载失败（检索不可用）: {e}")
            _rag_tools = []
            _rag_executor = lambda n, a: "[RAG] 不可用"


class MultiAgentOrchestrator:
    """LangGraph 多智能体编排器（Send API 并行版）"""

    def __init__(self, llm_client: LLMClient = None):
        if llm_client is None:
            llm_client = LLMClient()
        self._llm = llm_client
        self._memory = SlidingMemory()
        self._speed_ctrl = SpeedController()
        self._agents = {
            "tactical": TacticalAnalyst(LLMClient(model="qwen-plus", temperature=0.1)),
            "defense": DefenseSpecialist(LLMClient(model="qwen-plus", temperature=0.1)),
            "skill_officer": SkillOfficer(LLMClient(model="qwen-plus", temperature=0.1)),
            "chief": ChiefStrategist(LLMClient(model="qwen-plus", temperature=0.1)),
        }
        self._quick_llm = LLMClient(model="qwen-plus", temperature=0.1)
        self._extractor: Optional[GameInfoExtractor] = None
        self._graph = self._build_graph()

    # ==================== 快速开局通道 ====================

    def _quick_opening_move(self, game_report: str, turn_count: int,
                            current_color: str, board) -> FinalDecision:
        """回合 1-4 的快速开局决策：第1步硬编码中心，第2-4步单次 LLM"""
        _log.info(f"快速开局通道: turn={turn_count}, color={current_color}")

        if turn_count == 1:
            x, y = self._pick_center_or_nearby(board)
            return FinalDecision(
                move=(x, y),
                reason="开局第一步：占天元（中心）最优，若被占则取邻位",
                agent_summaries={"quick_opening": "硬编码天元/邻位"},
            )

        prompt = (
            "你是五子棋开局专家。根据当前局面，给出一个合理的开局落子。\n"
            "职业规则：优先中心区域，积极构造活二、活三。不必过度防守。\n"
            "输出JSON: {\"move\": [x,y], \"reasoning\": \"...\", \"confidence\": 0.0-1.0}\n"
            "规则：只能在 . 空位落子，严禁选 X/O/* 格。"
        )
        raw = self._quick_llm.chat(prompt, game_report, response_format="json_object")
        reason = "开局快速决策"
        summary = ""
        try:
            import json
            data = json.loads(raw)
            move = data.get("move", [7, 7])
            if isinstance(move, list) and len(move) == 2:
                x, y = int(move[0]), int(move[1])
            else:
                x, y = 7, 7
            reason = data.get("reasoning", reason)
            summary = data.get("reasoning", "")
        except Exception:
            x, y = 7, 7

        if not board.is_empty(x, y):
            _log.warning(f"快速开局 LLM 返回非法位置 ({x},{y})，使用邻位兜底")
            x, y = self._pick_center_or_nearby(board)

        return FinalDecision(
            move=(x, y),
            reason=reason,
            agent_summaries={"quick_opening": summary},
        )

    def _pick_center_or_nearby(self, board) -> tuple:
        """选择中心空位，若被占则选邻位"""
        if board.is_empty(7, 7):
            return (7, 7)
        neighbors = [(6, 7), (7, 6), (6, 6), (8, 7), (7, 8), (8, 8), (6, 8), (8, 6)]
        for nx, ny in neighbors:
            if board.is_empty(nx, ny):
                return (nx, ny)
        import random
        empty = board.get_empty_positions()
        if empty:
            pos = random.choice(empty)
            return (pos.x, pos.y)
        return (7, 7)

    # ==================== 算法预检 ====================

    def _algorithm_precheck(self, controller) -> Optional[FinalDecision]:
        """在 LLM 流水线之前进行算法级检查。

        若发现强制落子（必胜或必堵），直接返回决策，跳过 LLM 分析。
        若发现严重威胁，返回警告信息但不跳过 LLM。

        Returns:
            FinalDecision —— 强制落子决策（跳过 LLM）
            None —— 无强制落子，继续走 LLM 流水线
        """
        grid = controller.board.grid
        blocked = {(p.x, p.y) for p in controller.board.get_blocked_positions()}
        current = controller.current_player.color
        opponent = controller.opponent_player.color

        # 1. 己方必胜点 —— 直接落子
        own_win = find_immediate_win(grid, current, blocked)
        if own_win:
            _log.info(f"算法预检: 己方必胜点 {own_win}，跳过 LLM")
            return FinalDecision(
                move=own_win,
                reason=f"算法检测：己方在 {own_win} 落子即五连获胜",
                agent_summaries={"algorithm": "immediate_win"},
            )

        # 2. 对手必胜点 —— 必须封堵
        opp_win = find_must_block(grid, opponent, blocked)
        if opp_win:
            _log.info(f"算法预检: 必须封堵 {opp_win}，跳过 LLM")
            return FinalDecision(
                move=opp_win,
                reason=f"算法检测：对手在 {opp_win} 落子即五连，必须封堵",
                agent_summaries={"algorithm": "must_block"},
            )

        # 3. 己方双重威胁 —— 也是必胜（优先于封堵对手活三）
        own_double = find_double_threat_moves(grid, current, blocked)
        if own_double:
            from ..algorithm import score_position
            best = max(own_double, key=lambda m: score_position(
                grid, m[0], m[1], current, blocked))
            _log.info(f"算法预检: 己方双重威胁 {best}，跳过 LLM")
            return FinalDecision(
                move=best,
                reason=f"算法检测：己方在 {best} 形成双重威胁（双活三/活三+冲四），对手无法同时防守",
                agent_summaries={"algorithm": "double_threat"},
            )

        # 4. 对手已有活三 —— 必须封堵一端，否则下一步变活四
        opp_live3_blocks = find_existing_live3_blocks(grid, opponent, blocked)
        if opp_live3_blocks:
            from ..algorithm import score_position
            best = max(opp_live3_blocks, key=lambda m: score_position(
                grid, m[0], m[1], current, blocked))
            _log.info(f"算法预检: 封堵对手活三 {best}，跳过 LLM")
            return FinalDecision(
                move=best,
                reason=f"算法检测：对手已有活三（三子连线+两端空），必须在 {best} 封堵，否则对手下一步活四必胜",
                agent_summaries={"algorithm": "block_live3"},
            )

        return None

    # ==================== 对外接口 ====================

    def analyze(self, controller, human_question: str = "") -> FinalDecision:
        """执行一次完整的多智能体分析，返回最终决策。

        带校验-警告-重试循环：若 AI 落子位置非法，在 game_report 末尾附加
        警告信息后重新调用，最多重试 3 次。
        """
        self._extractor = GameInfoExtractor(controller)
        base_report = self._extractor.build_game_report()

        # 算法预检：强制落子（必胜/必堵）直接返回，跳过 LLM
        precheck = self._algorithm_precheck(controller)
        if precheck is not None:
            return precheck

        # 快速开局通道：第1步硬编码，第2-4步单次LLM
        if controller.turn_count <= 4:
            decision = self._quick_opening_move(
                base_report, controller.turn_count,
                controller.current_player.color,
                controller.board)
            # 校验快速开局落子合法性（兜底保护）
            x, y = decision.move
            if not controller.board.is_empty(x, y):
                _log.warning(f"快速开局返回非法位置 ({x},{y})，使用随机空位兜底")
                import random
                empty = controller.board.get_empty_positions()
                if empty:
                    pos = random.choice(empty)
                    decision = FinalDecision(
                        move=(pos.x, pos.y),
                        reason="快速开局兜底",
                        agent_summaries={"quick_opening": "fallback"},
                    )
            return decision

        # RAG 棋谱检索（turn >= 5 时启用）
        if controller.turn_count >= 5:
            _init_rag()
            if _rag_tools:
                try:
                    rag_ctx = self._extractor.get_rag_context()
                    if rag_ctx:
                        base_report += f"\n\n{rag_ctx}"
                except Exception:
                    pass  # RAG 失败不影响主流程

        mem_ctx = self._memory.get_context_for_prompt()
        if mem_ctx:
            base_report += f"\n\n【历史背景】\n{mem_ctx}"

        max_retries = 3
        warning = ""

        for attempt in range(max_retries + 1):
            game_report = base_report + warning

            _log.info(f"开始分析 turn={controller.turn_count}, "
                      f"color={controller.current_player.color}, "
                      f"attempt={attempt + 1}")

            initial_state: MultiAgentState = {
                "game_report": game_report,
                "turn_count": controller.turn_count,
                "current_color": controller.current_player.color,
                "tactical_proposal": None,
                "defense_proposal": None,
                "skill_decision": None,
                "chief_decision": None,
                "messages": [],
                "human_question": human_question,
                "is_rethinking": bool(human_question),
                "phase": "normal",
                "_join_counter": 0,
                "algorithm_analysis": "",
            }
            result = self._graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": f"game_{controller.turn_count}_r{attempt}"}},
            )
            decision = self._extract_decision(result)

            # 校验落子合法性
            x, y = decision.move
            if controller.board.is_empty(x, y):
                _log.info(f"分析完成: move={decision.move}, phase={result.get('phase','?')}")
                return decision

            # 位置非法——附加警告并重试
            _log.warning(f"AI 返回非法位置 ({x},{y})，第 {attempt + 1} 次重试")
            reason = _explain_invalid(x, y, controller.board)
            warning = (f"\n\n!!! 警告（第{attempt + 1}次）: 你上次选的 ({x},{y}) {reason}。"
                       f"请仔细看棋盘，只能选 . 空位。禁止选 X/O/* 格。")

        # 全部重试失败：算法搜索兜底
        _log.warning("重试耗尽，启用算法搜索兜底")
        grid = controller.board.grid
        blocked = {(p.x, p.y) for p in controller.board.get_blocked_positions()}
        current = controller.current_player.color
        algo_move = get_best_move(grid, current, blocked, depth=2, time_limit=0.5)
        if algo_move:
            _log.warning(f"算法搜索兜底: {algo_move}")
            return FinalDecision(
                move=algo_move,
                reason="警告机制：AI 3次均返回非法位置，算法搜索兜底",
                agent_summaries={"algorithm": "fallback_search"},
            )
        # 最后手段：随机空位
        import random
        empty = controller.board.get_empty_positions()
        if empty:
            fallback = random.choice(empty)
            _log.warning(f"算法搜索无结果，随机兜底: {fallback}")
            return FinalDecision(
                move=(fallback.x, fallback.y),
                reason="算法搜索无结果，随机选取空位兜底",
                agent_summaries={},
            )
        return FinalDecision(
            move=(7, 7),
            reason="警告机制：无可用空位",
            agent_summaries={},
        )

    # ==================== Node 函数 ====================

    def _phase_check_node(self, state: MultiAgentState) -> dict:
        phase = self._speed_ctrl.classify_phase(
            state["game_report"], state["turn_count"])
        _log.debug(f"局势分级: {phase}")
        return {"phase": phase}

    def _tactical_node(self, state: MultiAgentState) -> dict:
        """战术官：进攻分析（LangGraph 独立节点，由 Send fan-out 并行调度）"""
        _log.debug("战术官分析中...")
        if _rag_tools:
            proposal = self._agents["tactical"].think_with_tools(
                state["game_report"], _rag_tools, _rag_executor)
        else:
            proposal = self._agents["tactical"].think(state["game_report"])
        if proposal:
            _log.info(f"战术官: move={proposal.move}, "
                      f"confidence={proposal.confidence:.2f}")
            return {"tactical_proposal": proposal.to_dict()}
        return {}

    def _defense_node(self, state: MultiAgentState) -> dict:
        """防守官：防守分析（LangGraph 独立节点，由 Send fan-out 并行调度）"""
        _log.debug("防守官分析中...")
        if _rag_tools:
            proposal = self._agents["defense"].think_with_tools(
                state["game_report"], _rag_tools, _rag_executor)
        else:
            proposal = self._agents["defense"].think(state["game_report"])
        if proposal:
            _log.info(f"防守官: move={proposal.move}, "
                      f"confidence={proposal.confidence:.2f}")
            return {"defense_proposal": proposal.to_dict()}
        return {}

    def _post_analysis_node(self, state: MultiAgentState) -> dict:
        """并行fan-out后的join节点。

        LangGraph 的 Send fan-out 会将 tactical 和 defense 的结果写入共享 state。
        两个节点都连接到 post_analysis，需用计数器确保只在两次调用中的第二次才执行实际逻辑。
        """
        count = state.get("_join_counter", 0) + 1
        if count < 2:
            # 第一个完成的 Agent 到达，等待另一个
            _log.debug(f"post_analysis 等待 ({count}/2)")
            return {"_join_counter": count}

        _log.debug("post_analysis: 两个Agent均已完成，开始裁决")

    def _skill_officer_node(self, state: MultiAgentState) -> dict:
        """技能使用官：阅读当前局势，裁决是否使用主动技能"""
        _log.debug("技能使用官分析中...")
        ctrl = self._extractor.ctrl
        player = ctrl.current_player
        skill_tool = get_skill_tool(player)
        own_skill = f"{player.skill.skill_name}({player.skill.description})" if player.skill else ""

        proposals = {}
        if state.get("tactical_proposal"):
            proposals["tactical"] = state["tactical_proposal"]
        if state.get("defense_proposal"):
            proposals["defense"] = state["defense_proposal"]

        if skill_tool:
            def skill_executor(tool_name, arguments):
                return (f"[技能预览] 将在落子前激活 {player.skill.skill_name}"
                        f" 参数: {arguments}" if arguments else
                        f"[技能预览] 将在落子前激活 {player.skill.skill_name}")
            decision = self._agents["skill_officer"].think_with_skill_tool(
                state["game_report"], skill_tool, skill_executor,
                proposals=proposals, own_skill=own_skill)
        else:
            from ..core.protocol import SkillDecision
            decision = SkillDecision(reasoning="无主动技能")

        if decision and decision.activate_skill:
            _log.info(f"技能使用官裁决: 激活技能 {decision.activate_skill}")
        else:
            _log.info(f"技能使用官裁决: 不使用技能")
        return {"skill_decision": decision.to_dict() if decision else None}

    def _chief_node(self, state: MultiAgentState) -> dict:
        _log.debug("总策划官裁决中...")
        proposals = {}
        if state.get("tactical_proposal"):
            proposals["tactical"] = state["tactical_proposal"]
        if state.get("defense_proposal"):
            proposals["defense"] = state["defense_proposal"]

        skill_decision = state.get("skill_decision")

        decision = self._agents["chief"].think(
            state["game_report"], proposals=proposals,
            skill_decision=skill_decision)

        if decision:
            _log.info(f"总策划官裁决: move={decision.move}")
        return {"chief_decision": decision.to_dict() if decision else None}

    def _consensus_node(self, state: MultiAgentState) -> dict:
        """战术官和防守官共识，直接采纳，无需 chief"""
        tac = state.get("tactical_proposal", {})
        df = state.get("defense_proposal", {})
        move = tac.get("move", [7, 7])
        _log.info(f"共识达成: move={move}, 跳过总策划官")
        return {
            "chief_decision": {
                "move": move,
                "reason": (f"战术官与防守官共识落子 {move} (confidence: "
                           f"tac={tac.get('confidence', 0):.2f}, "
                           f"def={df.get('confidence', 0):.2f})"),
                "agent_summaries": {
                    "tactical": tac.get("reasoning", ""),
                    "defense": df.get("reasoning", ""),
                },
            },
        }

    # ==================== 条件路由 ====================

    def _fanout_or_skip(self, state: MultiAgentState) -> list[Send]:
        """phase_check 之后直接并发 fan-out：tactical 和 defense 并行执行"""
        _log.debug("Send fan-out: tactical || defense")
        return [
            Send("tactical", state),
            Send("defense", state),
        ]

    def _route_after_join(self, state: MultiAgentState) -> str:
        """post_analysis join 之后的裁决路由。

        由于 post_analysis 的 _join_counter < 2 时提前返回（返回 {} 而非路由），
        此函数只在第二次调用（counter=2）时被触发。
        """
        tac = state.get("tactical_proposal") or {}
        df = state.get("defense_proposal") or {}

        # 检查共识
        tac_move = tuple(tac["move"]) if tac.get("move") and len(tac["move"]) == 2 else None
        df_move = tuple(df["move"]) if df.get("move") and len(df["move"]) == 2 else None
        tac_conf = tac.get("confidence", 0)
        df_conf = df.get("confidence", 0)

        if (tac_move and df_move and tac_move == df_move
                and tac_conf > 0.8 and df_conf > 0.8):
            _log.info(f"检测到共识: {tac_move}, 跳过后续流程")
            return "consensus"

        return "skill_officer"

    # ==================== 图构建 ====================

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(MultiAgentState)

        # 节点注册
        builder.add_node("phase_check", self._phase_check_node)
        builder.add_node("tactical", self._tactical_node)
        builder.add_node("defense", self._defense_node)
        builder.add_node("post_analysis", self._post_analysis_node)
        builder.add_node("skill_officer", self._skill_officer_node)
        builder.add_node("chief", self._chief_node)
        builder.add_node("consensus", self._consensus_node)

        # 图结构
        builder.add_edge(START, "phase_check")

        # phase_check → [Send(tactical) || Send(defense)] 直接并发
        builder.add_conditional_edges("phase_check", self._fanout_or_skip, {})

        # tactical 和 defense 并行执行后汇聚到 post_analysis
        builder.add_edge("tactical", "post_analysis")
        builder.add_edge("defense", "post_analysis")

        # post_analysis 作为 join + 路由节点
        builder.add_conditional_edges("post_analysis", self._route_after_join, {
            "consensus": "consensus",
            "skill_officer": "skill_officer",
        })

        builder.add_edge("consensus", END)
        builder.add_edge("skill_officer", "chief")
        builder.add_edge("chief", END)

        return builder.compile(checkpointer=MemorySaver())

    # ==================== 决策提取 ====================

    def _extract_decision(self, result: dict) -> FinalDecision:
        cd = result.get("chief_decision") or {}
        move_raw = cd.get("move", [7, 7])
        if isinstance(move_raw, list) and len(move_raw) == 2:
            move = (int(move_raw[0]), int(move_raw[1]))
        else:
            move = (7, 7)

        sd = result.get("skill_decision") or {}
        activate_skill = sd.get("activate_skill")

        decision = FinalDecision(
            move=move,
            reason=cd.get("reason", ""),
            agent_summaries=cd.get("agent_summaries", {}),
            activate_skill=activate_skill,
        )

        self._memory.add_turn({
            "turn": result.get("turn_count", 0),
            "move": f"({move[0]},{move[1]})",
        })

        return decision
