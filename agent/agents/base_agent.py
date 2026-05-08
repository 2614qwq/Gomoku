"""Agent 抽象基类 —— 模板方法模式"""

from abc import ABC, abstractmethod
from ..llm_client import LLMClient


class BaseAgent(ABC):
    """所有 Agent 的抽象基类。子类只需提供视角差异（提示词、解析方式）"""

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    @property
    @abstractmethod
    def role_name(self) -> str: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def build_user_message(self, game_report: str, **context) -> str: ...

    @abstractmethod
    def parse_response(self, text: str):
        """解析 LLM 文本为 Proposal / Critique / FinalDecision"""

    def think(self, game_report: str, **context):
        """模板方法：LLM 调用 → 解析 → 返回结构化结果"""
        user_msg = self.build_user_message(game_report, **context)
        raw = self._llm.chat(self.system_prompt, user_msg,
                            response_format="json_object")
        return self.parse_response(raw)
