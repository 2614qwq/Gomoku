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

    def think_with_tools(self, game_report: str, tools: list[dict],
                         tool_executor, **context):
        """带 tool-calling 的思考方法（泛化设计，不耦合具体 RAG 实现）

        Args:
            game_report: 当前局面文本
            tools: OpenAI tool schema 列表
            tool_executor: callable(name, arguments) -> str，执行 tool 并返回结果
            **context: 传递给 build_user_message 的额外参数

        Returns: 同 parse_response()
        """
        user_msg = self.build_user_message(game_report, **context)
        resp = self._llm.chat_with_tools(self.system_prompt, user_msg, tools)

        # 如果 LLM 调用了 tool，执行后追加结果再问一次
        if resp.get("tool_calls"):
            for tc in resp["tool_calls"]:
                tool_result = tool_executor(tc["name"], tc["arguments"])
                # 构造第二轮消息
                followup = (
                    f"{user_msg}\n\n"
                    f"[工具调用: {tc['name']}]\n"
                    f"参数: {tc['arguments']}\n"
                    f"结果:\n{tool_result}\n\n"
                    f"请结合以上检索结果，重新给出你的建议并输出JSON。"
                )
                raw = self._llm.chat(self.system_prompt, followup,
                                    response_format="json_object")
                return self.parse_response(raw)

        # 未调用 tool，直接解析
        content = resp.get("content") or ""
        return self.parse_response(content)
