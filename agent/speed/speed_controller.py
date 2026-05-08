"""SpeedController —— 局势分级 + 候选过滤 + 超时熔断"""

import asyncio


class SpeedController:
    """决定走哪个流程分支。只有紧急情况才跳过 LLM。"""

    AGENT_TIMEOUT = 3.0
    TOTAL_TIMEOUT = 8.0
    QUESTION_TIMEOUT = 5.0

    def classify_phase(self, game_report: str, turn_count: int) -> str:
        """局势分级。

        emergency: 对手有四连 → 跳过 LLM，引擎直接防守
        complex:   多威胁并存 → 全流程（含反对官）
        normal:    一般局势 → 战术+防守+总策划，跳过反对官
        simple:    无明显威胁 → 战术+防守+总策划，快速通过

        注意: simple/normal/complex 都会走 LLM，只有 emergency 跳过。
        """
        if "对方四连" in game_report and "处" in game_report:
            return "emergency"

        threat_count = game_report.count("三连") + game_report.count("四连")
        if threat_count >= 3:
            return "complex"
        if threat_count >= 1:
            return "normal"
        return "simple"

    def get_top_candidates(self, board, color: str, n: int = 8) -> list:
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from engine import evaluate_position
            scored = []
            for y in range(15):
                for x in range(15):
                    if board.get(x, y) == ' ':
                        s = evaluate_position(board.grid, x, y, color)
                        scored.append(((x, y), s))
            scored.sort(key=lambda v: v[1], reverse=True)
            return scored[:n]
        except Exception:
            return []

    async def execute_with_timeout(self, coro, timeout: float = None):
        if timeout is None:
            timeout = self.AGENT_TIMEOUT
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return None
