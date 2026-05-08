"""技能使用官 —— 阅读当前局势，裁决是否使用主动技能"""

import json
from .base_agent import BaseAgent
from ..core.protocol import SkillDecision
from ..prompts import PromptLoader

_PROMPTS = PromptLoader()


class SkillOfficer(BaseAgent):
    """阅读当前局势和己方技能，决定是否使用以及如何使用"""

    @property
    def role_name(self) -> str:
        return "技能使用官"

    @property
    def system_prompt(self) -> str:
        return _PROMPTS.get("skill_officer")

    def build_user_message(self, game_report: str, **context) -> str:
        proposals = context.get("proposals", {})
        own_skill = context.get("own_skill", "")

        parts = [game_report]
        if own_skill:
            parts.append(f"己方主动招式: {own_skill}")
        if proposals:
            parts.append("Agent提案参考:")
            for role, p in proposals.items():
                if p:
                    parts.append(f"  {role}: ({p.get('move')}) {p.get('reasoning','')}")
        parts.append("请裁决是否使用主动技能，输出JSON。")
        return "\n\n".join(parts)

    def parse_response(self, text: str) -> SkillDecision:
        try:
            data = json.loads(text)
            activate = data.get("activate_skill")
            reasoning = data.get("reasoning", "")
            return SkillDecision(
                activate_skill=activate,
                reasoning=reasoning,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return SkillDecision()

    def think_with_skill_tool(self, game_report: str, skill_tool: dict,
                               skill_executor, **context):
        tools = [skill_tool] if skill_tool else []
        return self.think_with_tools(game_report, tools, skill_executor, **context)
