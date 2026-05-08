"""LangGraph 图状态定义"""

from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class MultiAgentState(TypedDict, total=False):
    """在 LangGraph Node 之间流转的共享 State"""

    # ---- 游戏上下文 ----
    game_report: str
    turn_count: int
    current_color: str              # 'X' / 'O'

    # ---- Agent 输出 ----
    tactical_proposal: Optional[dict]
    defense_proposal: Optional[dict]
    devil_critiques: Optional[list]
    chief_decision: Optional[dict]

    # ---- 对话历史 (reducer 追加) ----
    messages: Annotated[list[BaseMessage], add_messages]

    # ---- 反问 ----
    human_question: str
    is_rethinking: bool

    # ---- 速度控制 ----
    phase: str                      # "emergency" / "simple" / "normal" / "complex"
    skip_llm: bool

    # ---- 内部：并行fan-out后join计数 ----
    _join_counter: int
