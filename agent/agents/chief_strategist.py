"""总策划官 —— 汇总所有意见，做出最终裁决"""

import json
from .base_agent import BaseAgent
from ..core.protocol import FinalDecision
from ..prompts import PromptLoader

_PROMPTS = PromptLoader()


class ChiefStrategist(BaseAgent):
    """阅读全部 Agent 输出，综合评估，输出最终落子"""

    @property
    def role_name(self) -> str:
        return "总策划官"

    @property
    def system_prompt(self) -> str:
        return _PROMPTS.get("chief")

    def build_user_message(self, game_report: str, **context) -> str:
        proposals = context.get("proposals", {})
        skill_decision = context.get("skill_decision")

        parts = [game_report]
        if proposals:
            parts.append("Agent提案:")
            for role, p in proposals.items():
                if p:
                    parts.append(f"  {role}: ({p.get('move')}) {p.get('reasoning','')}")
        if skill_decision:
            sd = skill_decision
            if isinstance(sd, dict) and sd.get("activate_skill"):
                parts.append(f"技能使用官已决定激活技能: {sd.get('reasoning','')}")
            elif isinstance(sd, dict):
                parts.append(f"技能使用官决定不激活技能: {sd.get('reasoning','')}")
        parts.append("请汇总裁决，输出最终落子JSON。")
        return "\n\n".join(parts)

    def parse_response(self, text: str) -> FinalDecision:
        try:
            data = json.loads(text)
            move = tuple(data["move"]) if isinstance(data["move"], list) else (7, 7)
            return FinalDecision(
                move=move,
                reason=data.get("reason", ""),
                agent_summaries=data.get("agent_summaries", {}),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            from ..llm_client import LLMClient
            client = LLMClient()
            parsed = client.parse_move(text)
            move = parsed if parsed else (7, 7)
            return FinalDecision(move=move, reason=text[:100])
