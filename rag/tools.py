"""Tool 注册表 —— 管理所有 RAG 检索工具

支持注册、查找、执行。后续添加新材料检索工具只需 register() 即可。
"""

from typing import Callable, Any


class ToolRegistry:
    """Tool 注册表：schema + handler 绑定，统一执行入口"""

    def __init__(self):
        self._schemas: list[dict] = []
        self._handlers: dict[str, Callable[[dict], str]] = {}

    def register(self, name: str, schema: dict, handler: Callable[[dict], str]):
        """注册一个 tool

        Args:
            name: tool 名称（与 schema.function.name 一致）
            schema: OpenAI tool schema dict
            handler: 执行函数，接收参数字典，返回结果字符串
        """
        self._schemas.append(schema)
        self._handlers[name] = handler

    def get_schemas(self) -> list[dict]:
        """获取所有 tool schema（传给 LLM）"""
        return list(self._schemas)

    def execute(self, name: str, arguments: dict) -> str:
        """执行指定 tool，返回结果文本"""
        handler = self._handlers.get(name)
        if handler is None:
            return f"[Tool] 未找到: {name}"
        try:
            return handler(arguments)
        except Exception as e:
            return f"[Tool] 执行失败 ({name}): {e}"

    @property
    def tool_names(self) -> list[str]:
        return list(self._handlers.keys())
