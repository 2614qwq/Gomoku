"""战术官 —— 进攻分析 + 己方技能优化"""

import json
import os
from .base_agent import BaseAgent
from ..core.protocol import Proposal
from ..prompts import PromptLoader

_PROMPTS = PromptLoader()


class TacticalAnalyst(BaseAgent):
    """找进攻机会，结合己方技能调整策略"""

    @property
    def role_name(self) -> str:
        return "战术官"

    @property
    def system_prompt(self) -> str:
        return _PROMPTS.get("tactical")

    def build_user_message(self, game_report: str, **context) -> str:
        return f"{game_report}\n\n进攻视角：推荐最佳落子（JSON）。"

    def parse_response(self, text: str) -> Proposal:
        try:
            data = json.loads(text)
            move = tuple(data["move"]) if isinstance(data["move"], list) else (7, 7)
            return Proposal(
                agent_role=self.role_name,
                move=move,
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.5)),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            from ..llm_client import LLMClient
            client = LLMClient()
            parsed = client.parse_move(text)
            move = parsed if parsed else (7, 7)
            return Proposal(
                agent_role=self.role_name,
                move=move,
                reasoning=text[:100],
                confidence=0.3,
            )
