"""agent — 五子棋多智能体协作系统

基于 LangGraph 编排，四 Agent 协作决策。
"""

from .llm_client import LLMClient
from .core.orchestrator import MultiAgentOrchestrator
from .core.protocol import Proposal, Critique, FinalDecision

# 向后兼容
GomokuAgent = MultiAgentOrchestrator

__all__ = [
    "LLMClient",
    "MultiAgentOrchestrator",
    "GomokuAgent",
    "Proposal", "Critique", "FinalDecision",
]
