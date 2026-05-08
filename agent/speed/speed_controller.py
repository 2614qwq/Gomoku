"""SpeedController —— 局势分级 + 超时熔断"""

import asyncio


class SpeedController:
    """根据局势复杂度分级。全流程由 AI 负责，无引擎兜底。"""

    AGENT_TIMEOUT = 3.0
    TOTAL_TIMEOUT = 8.0
    QUESTION_TIMEOUT = 5.0

    def classify_phase(self, game_report: str, turn_count: int) -> str:
        """局势分级。

        opening: 前4步快速开局 → orchestrator 硬编码/单次LLM
        complex: 多威胁并存 → 全流程（含技能使用官+总策划官）
        normal:  一般局势 → 战术+防守+总策划
        """
        if turn_count <= 4:
            return "opening"
        threat_count = game_report.count("三连") + game_report.count("四连")
        if threat_count >= 3:
            return "complex"
        return "normal"

    async def execute_with_timeout(self, coro, timeout: float = None):
        if timeout is None:
            timeout = self.AGENT_TIMEOUT
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return None
