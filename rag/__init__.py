"""RAG 知识检索模块 —— 懒加载单例入口

用法:
    from rag import get_retriever, get_tools

    retriever = get_retriever()       # OpeningRetriever 单例
    tools = get_tools(retriever)      # ToolRegistry + 已注册 tools
"""

from typing import Optional
from .retriever import OpeningRetriever
from .tools import ToolRegistry

_retriever: Optional[OpeningRetriever] = None
_tools: Optional[ToolRegistry] = None


def get_retriever() -> OpeningRetriever:
    """获取 OpeningRetriever 懒加载单例"""
    global _retriever
    if _retriever is None:
        _retriever = OpeningRetriever()
    return _retriever


def get_tools(retriever: Optional[OpeningRetriever] = None) -> ToolRegistry:
    """获取 ToolRegistry 单例，自动注册所有 RAG tools"""
    global _tools
    if _tools is None:
        r = retriever or get_retriever()
        _tools = ToolRegistry()
        _tools.register("search_chess_openings",
                        _make_openings_schema(),
                        lambda args: _search_openings_handler(args, r))
    return _tools


# ---- 内部：tool schema 与 handler ----

def _make_openings_schema() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "search_chess_openings",
            "description": (
                "检索与当前棋局最相似的专业棋谱开局/定式。"
                "输入当前已落子的前若干手序列，返回职业棋谱中相似局面及后续走向。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "current_moves": {
                        "type": "string",
                        "description": (
                            "当前棋局的前N手落子序列，格式: '黑1(x,y) 白2(x,y) 黑3(x,y) ...'。"
                            "例如: '黑1(7,7) 白2(7,8) 黑3(8,7)'"
                        ),
                    }
                },
                "required": ["current_moves"],
            },
        },
    }


def _search_openings_handler(args: dict, retriever: OpeningRetriever) -> str:
    current_moves = args.get("current_moves", "")
    if not current_moves:
        return "[RAG] 未提供当前落子序列，无法检索。"
    results = retriever.search(current_moves, top_k=3)
    if not results:
        return "[RAG] 未找到相似棋谱。"
    return retriever.format_context(results)
