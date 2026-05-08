"""防守官 —— 防守分析 + 敌方技能预警"""

import json
from .base_agent import BaseAgent
from ..core.protocol import Proposal
from ..prompts import PromptLoader

_PROMPTS = PromptLoader()


class DefenseSpecialist(BaseAgent):
    """找对手威胁，结合敌方技能做风险预警"""

    @property
    def role_name(self) -> str:
        return "防守官"

    @property
    def system_prompt(self) -> str:
        return _PROMPTS.get("defense")

    def build_user_message(self, game_report: str, **context) -> str:
        return (f"{game_report}\n\n"
                f"请从防守和敌方技能角度推荐最佳落子，输出JSON。")

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
