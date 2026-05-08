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
        critiques = context.get("critiques", [])
        own_skill = context.get("own_skill", "")

        parts = [game_report]
        if own_skill:
            parts.append(f"己方招式可调用: {own_skill}")
        if proposals:
            parts.append("Agent提案:")
            for role, p in proposals.items():
                if p:
                    parts.append(f"  {role}: ({p.get('move')}) {p.get('reasoning','')}")
        if critiques:
            parts.append("反对意见:")
            for c in critiques:
                if isinstance(c, dict):
                    parts.append(f"  ({c.get('target_move')}): {c.get('concern','')}")
                else:
                    parts.append(f"  ({c.target_move}): {c.concern}")
        parts.append("请汇总裁决（可用 activate_skill 调用招式），输出JSON。")
        return "\n\n".join(parts)

    def parse_response(self, text: str) -> FinalDecision:
        try:
            data = json.loads(text)
            move = tuple(data["move"]) if isinstance(data["move"], list) else (7, 7)
            activate = None
            if data.get("activate_skill"):
                activate = data["activate_skill"]
            return FinalDecision(
                move=move,
                reason=data.get("reason", ""),
                agent_summaries=data.get("agent_summaries", {}),
                activate_skill=activate,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            from ..llm_client import LLMClient
            client = LLMClient()
            parsed = client.parse_move(text)
            move = parsed if parsed else (7, 7)
            return FinalDecision(move=move, reason=text[:100])

    def think_with_skill_tool(self, game_report: str, skill_tool: dict,
                               skill_executor, **context):
        """带技能 tool-calling 的思考方法"""
        tools = [skill_tool] if skill_tool else []
        return self.think_with_tools(game_report, tools, skill_executor, **context)
