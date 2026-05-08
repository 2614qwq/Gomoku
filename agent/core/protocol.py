"""消息协议 —— 多智能体之间传递的数据结构"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Proposal:
    """单个 Agent 的落子提案"""
    agent_role: str
    move: tuple[int, int]          # (x, y)
    reasoning: str
    confidence: float               # 0.0 ~ 1.0

    def to_dict(self) -> dict:
        return {
            "agent_role": self.agent_role,
            "move": list(self.move),
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


@dataclass
class Critique:
    """反对官对提案的批评"""
    target_move: tuple[int, int]
    concern: str
    severity: str                   # "fatal" / "serious" / "minor"

    def to_dict(self) -> dict:
        return {
            "target_move": list(self.target_move),
            "concern": self.concern,
            "severity": self.severity,
        }


@dataclass
class FinalDecision:
    """Chief 的最终决策"""
    move: tuple[int, int]
    reason: str
    agent_summaries: dict = field(default_factory=dict)
    activate_skill: dict = None  # {"name": str, "args": dict} | None

    def to_dict(self) -> dict:
        d = {
            "move": list(self.move),
            "reason": self.reason,
            "agent_summaries": self.agent_summaries,
        }
        if self.activate_skill:
            d["activate_skill"] = self.activate_skill
        return d
