"""GameInfoExtractor —— 从 GameController 提取 Agent 所需的文本报告"""

from ..board_codec import board_to_text


class GameInfoExtractor:
    """唯一直接访问 GameController 的类。生成 game_report 供所有 Agent 共用。"""

    def __init__(self, controller):
        self.ctrl = controller

    def build_game_report(self) -> str:
        sections = [
            self._turn_section(),
            self._occupied_section(),
            self._board_section(),
            self._own_skill_section(),
            self._enemy_skill_section(),
        ]
        return "\n\n".join(filter(None, sections))

    # ---- 各信息段落 ----

    def _turn_section(self) -> str:
        p = self.ctrl.current_player
        opp = self.ctrl.opponent_player
        return f"回合{self.ctrl.turn_count} #{p.name}({p.color}) vs {opp.name}({opp.color})"

    def _occupied_section(self) -> str:
        """列出已占据和封锁的坐标，供 LLM 直接避开"""
        board = self.ctrl.board
        black = []
        white = []
        blocked = []
        for y in range(15):
            for x in range(15):
                if board.is_blocked(x, y):
                    blocked.append(f"({x},{y})")
                elif board.get(x, y) == 'X':
                    black.append(f"({x},{y})")
                elif board.get(x, y) == 'O':
                    white.append(f"({x},{y})")
        parts = []
        if black:
            parts.append(f"X已占: {','.join(black)}")
        else:
            parts.append("X已占: 无")
        if white:
            parts.append(f"O已占: {','.join(white)}")
        else:
            parts.append("O已占: 无")
        if blocked:
            parts.append(f"封锁*: {','.join(blocked)}")
        return "\n".join(parts)

    def _board_section(self) -> str:
        blocked = {(p.x, p.y) for p in self.ctrl.board.get_blocked_positions()}
        legend = "15x15, .=空 X=黑 O=白 *=封锁, 坐标x=列(0-14) y=行(0-14)"
        return legend + "\n" + board_to_text(self.ctrl.board.grid, blocked=blocked)

    def _own_skill_section(self) -> str:
        skill = self.ctrl.current_player.skill
        if not skill:
            return ""
        return f"己方招式: {skill.skill_name}({skill.description})"

    def get_rag_context(self) -> str:
        """获取 RAG 棋谱参考上下文（由 orchestrator 调用）"""
        try:
            from rag import get_retriever
            retriever = get_retriever()
            results = retriever.search_by_grid(self.ctrl.board.grid, top_k=3)
            if results:
                return retriever.format_context(results)
        except Exception:
            pass
        return ""

    def _enemy_skill_section(self) -> str:
        skill = self.ctrl.opponent_player.skill
        if not skill:
            return ""
        blocked = [f"({x},{y})" for y in range(15) for x in range(15)
                   if self.ctrl.board.is_blocked(x, y)]
        info = f"敌方招式: {skill.skill_name}({skill.description})"
        if blocked:
            info += f" 封锁位: {','.join(blocked)}"
        return info
