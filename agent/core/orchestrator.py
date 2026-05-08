"""MultiAgentOrchestrator —— LangGraph StateGraph 编排器

优化版（使用 LangGraph 原生 Send API 实现并行）：
  - phase_check → [Send("tactical") || Send("defense")]  — LangGraph 原生 fan-out
  - post_analysis 作为 join 节点，汇总并行结果
  - simple / emergency 阶段跳过 LLM，直接使用引擎
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
from .protocol import FinalDecision, Proposal, Critique
from ..logger import get_logger

_log = get_logger("orchestrator")
from ..llm_client import LLMClient
from ..agents.tactical_analyst import TacticalAnalyst
from ..agents.defense_specialist import DefenseSpecialist
from ..agents.devil_advocate import DevilAdvocate
from ..agents.chief_strategist import ChiefStrategist
from ..game_info.extractor import GameInfoExtractor
from ..memory.sliding_memory import SlidingMemory
from ..speed.speed_controller import SpeedController


class MultiAgentOrchestrator:
    """LangGraph 多智能体编排器（Send API 并行版）"""

    def __init__(self, llm_client: LLMClient = None):
        if llm_client is None:
            llm_client = LLMClient()
        self._llm = llm_client
        self._memory = SlidingMemory()
        self._speed_ctrl = SpeedController()
        self._agents = {
            "tactical": TacticalAnalyst(LLMClient(model="qwen-turbo", temperature=0.1)),
            "defense": DefenseSpecialist(LLMClient(model="qwen-turbo", temperature=0.1)),
            "devil": DevilAdvocate(LLMClient(model="qwen-plus", temperature=0.1)),
            "chief": ChiefStrategist(LLMClient(model="qwen-plus", temperature=0.1)),
        }
        self._extractor: Optional[GameInfoExtractor] = None
        self._graph = self._build_graph()

    # ==================== 对外接口 ====================

    def analyze(self, controller, human_question: str = "") -> FinalDecision:
        """执行一次完整的多智能体分析，返回最终决策"""
        self._extractor = GameInfoExtractor(controller)
        game_report = self._extractor.build_game_report()

        mem_ctx = self._memory.get_context_for_prompt()
        if mem_ctx:
            game_report += f"\n\n【历史背景】\n{mem_ctx}"

        _log.info(f"开始分析 turn={controller.turn_count}, "
                  f"color={controller.current_player.color}, "
                  f"is_rethink={bool(human_question)}")

        initial_state: MultiAgentState = {
            "game_report": game_report,
            "turn_count": controller.turn_count,
            "current_color": controller.current_player.color,
            "tactical_proposal": None,
            "defense_proposal": None,
            "devil_critiques": None,
            "chief_decision": None,
            "messages": [],
            "human_question": human_question,
            "is_rethinking": bool(human_question),
            "phase": "normal",
            "skip_llm": False,
            "_join_counter": 0,
        }
        result = self._graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": f"game_{controller.turn_count}"}},
        )
        decision = self._extract_decision(result)
        _log.info(f"分析完成: move={decision.move}, phase={result.get('phase','?')}, "
                  f"skip_llm={result.get('skip_llm', False)}")
        return decision

    # ==================== Node 函数 ====================

    def _phase_check_node(self, state: MultiAgentState) -> dict:
        phase = self._speed_ctrl.classify_phase(
            state["game_report"], state["turn_count"])
        skip = phase in ("emergency", "simple")
        _log.debug(f"局势分级: {phase}, skip_llm={skip}")
        return {"phase": phase, "skip_llm": skip}

    def _engine_fallback_node(self, state: MultiAgentState) -> dict:
        _log.info(f"使用引擎兜底 (phase={state.get('phase', '?')})")
        try:
            from .. import engine
            color = state["current_color"]
            board_grid = self._extractor.ctrl.board.grid if self._extractor else None
            move = engine.get_best_move(board_grid, color) if board_grid else (7, 7)
        except Exception:
            move = (7, 7)
        phase_label = {"simple": "简单局面", "emergency": "紧急防守"}.get(
            state.get("phase", ""), "快速决策")
        return {
            "chief_decision": {
                "move": list(move),
                "reason": f"引擎{phase_label}",
                "agent_summaries": {},
            },
            "skip_llm": True,
        }

    def _tactical_node(self, state: MultiAgentState) -> dict:
        """战术官：进攻分析（LangGraph 独立节点，由 Send fan-out 并行调度）"""
        _log.debug("战术官分析中...")
        proposal = self._agents["tactical"].think(state["game_report"])
        if proposal:
            _log.info(f"战术官: move={proposal.move}, "
                      f"confidence={proposal.confidence:.2f}")
            return {"tactical_proposal": proposal.to_dict()}
        return {}

    def _defense_node(self, state: MultiAgentState) -> dict:
        """防守官：防守分析（LangGraph 独立节点，由 Send fan-out 并行调度）"""
        _log.debug("防守官分析中...")
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

    def _devil_advocate_node(self, state: MultiAgentState) -> dict:
        _log.debug("反对官分析中...")
        critiques = self._agents["devil"].think(
            state["game_report"],
            tactical=state.get("tactical_proposal"),
            defense=state.get("defense_proposal"),
        )
        if critiques:
            _log.info(f"反对官: {len(critiques)}条批评")
        return {"devil_critiques": [c.to_dict() for c in critiques] if critiques else []}

    def _chief_node(self, state: MultiAgentState) -> dict:
        _log.debug("总策划官裁决中...")
        proposals = {}
        if state.get("tactical_proposal"):
            proposals["tactical"] = state["tactical_proposal"]
        if state.get("defense_proposal"):
            proposals["defense"] = state["defense_proposal"]

        critiques_raw = state.get("devil_critiques") or []
        critiques = []
        for c in critiques_raw:
            if isinstance(c, dict):
                critiques.append(Critique(
                    target_move=tuple(c["target_move"]),
                    concern=c.get("concern", ""),
                    severity=c.get("severity", "minor"),
                ))

        decision = self._agents["chief"].think(
            state["game_report"], proposals=proposals, critiques=critiques)
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

    def _fanout_or_skip(self, state: MultiAgentState) -> Union[str, list[Send]]:
        """phase_check 之后的分发逻辑。

        - skip_llm=True → 直接走引擎兜底
        - 否则 → LangGraph Send fan-out：tactical 和 defense 并行执行
        """
        if state.get("skip_llm"):
            _log.debug("跳过 LLM，走引擎兜底")
            return "engine_fallback"

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

        if state.get("phase") == "complex":
            return "devil"
        return "chief"

    # ==================== 图构建 ====================

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(MultiAgentState)

        # 节点注册
        builder.add_node("phase_check", self._phase_check_node)
        builder.add_node("engine_fallback", self._engine_fallback_node)
        builder.add_node("tactical", self._tactical_node)
        builder.add_node("defense", self._defense_node)
        builder.add_node("post_analysis", self._post_analysis_node)
        builder.add_node("devil_advocate", self._devil_advocate_node)
        builder.add_node("chief", self._chief_node)
        builder.add_node("consensus", self._consensus_node)

        # 图结构
        builder.add_edge(START, "phase_check")

        # phase_check → engine_fallback 或 [Send(tactical) || Send(defense)]
        builder.add_conditional_edges("phase_check", self._fanout_or_skip, {
            "engine_fallback": "engine_fallback",
        })
        builder.add_edge("engine_fallback", END)

        # tactical 和 defense 并行执行后汇聚到 post_analysis
        builder.add_edge("tactical", "post_analysis")
        builder.add_edge("defense", "post_analysis")

        # post_analysis 作为 join + 路由节点
        builder.add_conditional_edges("post_analysis", self._route_after_join, {
            "consensus": "consensus",
            "devil": "devil_advocate",
            "chief": "chief",
        })

        builder.add_edge("consensus", END)
        builder.add_edge("devil_advocate", "chief")
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

        decision = FinalDecision(
            move=move,
            reason=cd.get("reason", ""),
            agent_summaries=cd.get("agent_summaries", {}),
        )

        self._memory.add_turn({
            "turn": result.get("turn_count", 0),
            "move": f"({move[0]},{move[1]})",
        })

        return decision
