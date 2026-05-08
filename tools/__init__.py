"""统一工具注册中心 —— 集中管理所有 Agent 可调用的 Tool

用法:
    from tools import get_tools
    registry = get_tools()
    schemas = registry.get_schemas()      # 传给 LLM
    result = registry.execute(name, args)  # 执行 tool

新增工具:
    1. 在 tools/ 下新建模块（如 tools/my_tools.py）
    2. 在 _register_all() 中 import 并调用 register_xxx(registry)
    —— 无需修改任何 agent 代码
"""

from typing import Callable


class ToolRegistry:
    """Tool 注册表：schema + handler 绑定，统一执行入口"""

    def __init__(self):
        self._schemas: list[dict] = []
        self._handlers: dict[str, Callable[[dict], str]] = {}

    def register(self, name: str, schema: dict, handler: Callable[[dict], str]):
        self._schemas.append(schema)
        self._handlers[name] = handler

    def get_schemas(self) -> list[dict]:
        """获取所有 tool schema（传给 LLM 的 tools 参数）"""
        return list(self._schemas)

    def execute(self, name: str, arguments: dict) -> str:
        """执行指定 tool，返回结果文本"""
        handler = self._handlers.get(name)
        if handler is None:
            return f"[Tool] 未注册: {name}"
        try:
            return handler(arguments)
        except Exception as e:
            return f"[Tool] 执行失败 ({name}): {e}"

    @property
    def tool_names(self) -> list[str]:
        return list(self._handlers.keys())


# ---- 单例 ----

_registry: ToolRegistry | None = None


def get_tools() -> ToolRegistry:
    """获取 ToolRegistry 全局单例（首次调用时自动注册所有 tool）"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_all(_registry)
    return _registry


def _register_all(registry: ToolRegistry):
    """注册所有 tool —— 后续新增工具只需在这里加一行"""
    from .rag_tools import register_rag_tools
    register_rag_tools(registry)
