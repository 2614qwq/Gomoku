"""RAG 棋谱检索 Tool —— search_chess_openings

注册到 ToolRegistry 中，供战术官/防守官通过 tool-calling 调用。
"""


def register_rag_tools(registry):
    """注册 search_chess_openings tool"""
    registry.register("search_chess_openings", _make_schema(), _handler)


def _make_schema() -> dict:
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


def _handler(args: dict) -> str:
    from rag import get_retriever

    current_moves = args.get("current_moves", "")
    if not current_moves:
        return "[RAG] 未提供当前落子序列，无法检索。"

    retriever = get_retriever()
    results = retriever.search(current_moves, top_k=3)
    if not results:
        return "[RAG] 未找到相似棋谱。"
    return retriever.format_context(results)
