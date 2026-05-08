"""反对官 —— 对前两名候选进行压力测试"""

import json
from .base_agent import BaseAgent
from ..core.protocol import Critique
from ..prompts import PromptLoader

_PROMPTS = PromptLoader()


class DevilAdvocate(BaseAgent):
    """不对棋盘做独立分析，只看战术官+防守官提案，专门找漏洞"""

    @property
    def role_name(self) -> str:
        return "反对官"

    @property
    def system_prompt(self) -> str:
        return _PROMPTS.get("devil_advocate")

    def build_user_message(self, game_report: str, **context) -> str:
        tactical = context.get("tactical", {})
        defense = context.get("defense", {})

        parts = [game_report]
        if tactical:
            parts.append(f"战术官推荐: ({tactical.get('move')}) — {tactical.get('reasoning','')}")
        if defense:
            parts.append(f"防守官推荐: ({defense.get('move')}) — {defense.get('reasoning','')}")
        parts.append("请对以上候选进行压力测试，输出JSON。")
        return "\n\n".join(parts)

    def parse_response(self, text: str) -> list:
        try:
            data = json.loads(text)
            critiques = data.get("critiques", [])
            return [
                Critique(
                    target_move=tuple(c["target_move"]),
                    concern=c.get("concern", ""),
                    severity=c.get("severity", "minor"),
                )
                for c in critiques[:2]  # 最多 2 条
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
