"""滑动窗口记忆"""

from collections import deque


class SlidingMemory:
    """两层记忆：
      短时记忆: 最近 10 步的决策摘要
      长时记忆: 最多 5 条关键事件（技能触发、四连威胁等）
    """

    def __init__(self, max_turns: int = 2, max_events: int = 2):
        self._turns: deque = deque(maxlen=max_turns)
        self._key_events: deque = deque(maxlen=max_events)

    def add_turn(self, turn_data: dict):
        """记录一步的决策摘要"""
        self._turns.append(turn_data)

    def add_key_event(self, event: str):
        self._key_events.append(event)

    def get_context_for_prompt(self, max_turns: int = 2, max_chars: int = 500) -> str:
        """获取压缩后的历史上下文，控制在 Token 预算内"""
        parts = []
        if self._key_events:
            parts.append("关键事件: " + " | ".join(self._key_events))
        recent = list(self._turns)[-max_turns:]
        if recent:
            parts.append("最近落子: " + " → ".join(
                f"第{t.get('turn','?')}步({t.get('move','?')})" for t in recent))
        text = "\n".join(parts)
        if len(text) > max_chars:
            text = text[:max_chars - 3] + "..."
        return text

    def reset(self):
        self._turns.clear()
        self._key_events.clear()
