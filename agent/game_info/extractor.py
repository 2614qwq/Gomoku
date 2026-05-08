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
            self._algorithm_section(),
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
        """列出已占据和封锁的坐标（紧凑格式），供 LLM 直接避开"""
        board = self.ctrl.board
        black = []
        white = []
        blocked = []
        for y in range(15):
            for x in range(15):
                if board.is_blocked(x, y):
                    blocked.append(f"{x},{y}")
                elif board.get(x, y) == 'X':
                    black.append(f"{x},{y}")
                elif board.get(x, y) == 'O':
                    white.append(f"{x},{y}")
        parts = []
        parts.append(f"X:{' '.join(black)}" if black else "X:无")
        parts.append(f"O:{' '.join(white)}" if white else "O:无")
        if blocked:
            parts.append(f"*:{' '.join(blocked)}")
        return " ".join(parts)

    def _board_section(self) -> str:
        blocked = {(p.x, p.y) for p in self.ctrl.board.get_blocked_positions()}
        legend = "15x15, .=空 X=黑 O=白 *=封锁, 坐标x=列(0-14) y=行(0-14)"
        return legend + "\n" + board_to_text(self.ctrl.board.grid, blocked=blocked)

    def _algorithm_section(self) -> str:
        """算法检测到的威胁分析，帮助 LLM 做出更准确的决策"""
        try:
            from agent.algorithm import (
                find_immediate_win, find_must_block,
                find_double_threat_moves, find_existing_live3_blocks,
                scan_threats,
            )
        except ImportError:
            return ""

        grid = self.ctrl.board.grid
        blocked = {(p.x, p.y) for p in self.ctrl.board.get_blocked_positions()}

        current = self.ctrl.current_player.color
        opponent = self.ctrl.opponent_player.color

        lines = ["【算法威胁分析】"]

        # 己方必胜点
        own_win = find_immediate_win(grid, current, blocked)
        if own_win:
            lines.append(f"!!! 己方必胜点: {own_win} —— 落子即五连！")

        # 对方必胜点 —— 必须堵
        opp_win = find_must_block(grid, opponent, blocked)
        if opp_win:
            lines.append(f"!!! 必须封堵: {opp_win} —— 对手落子即五连！")

        # 对方已有活三 —— 必须封堵一端
        opp_existing_live3 = find_existing_live3_blocks(grid, opponent, blocked)
        if opp_existing_live3:
            pts = " ".join(str(p) for p in opp_existing_live3[:6])
            lines.append(f"!!! 对手已有活三（三子连线+两端空），必须封堵一端: {pts}")

        # 己方双重威胁
        own_double = find_double_threat_moves(grid, current, blocked)
        if own_double:
            pts = " ".join(str(p) for p in own_double[:5])
            lines.append(f"己方双重威胁点（双活三/活三+冲四/活四）: {pts}")

        # 对方威胁扫描
        opp_threats = scan_threats(grid, opponent, blocked)
        if opp_threats["live4_spots"]:
            pts = " ".join(str(p) for p in opp_threats["live4_spots"][:3])
            lines.append(f"对手可形成活四的点: {pts}")
        if opp_threats["double_threats"]:
            pts = " ".join(str(p) for p in opp_threats["double_threats"][:5])
            lines.append(f"对手可形成双重威胁的点: {pts}")
        if opp_threats["rush4_spots"]:
            pts = " ".join(str(p) for p in opp_threats["rush4_spots"][:5])
            lines.append(f"对手可形成冲四的点: {pts}")
        if opp_threats["live3_spots"]:
            pts = " ".join(str(p) for p in opp_threats["live3_spots"][:5])
            lines.append(f"对手可形成活三的点: {pts}")

        # 己方进攻机会
        own_threats = scan_threats(grid, current, blocked)
        if own_threats["live4_spots"]:
            pts = " ".join(str(p) for p in own_threats["live4_spots"][:3])
            lines.append(f"己方可形成活四的点: {pts}")
        if own_threats["rush4_spots"]:
            pts = " ".join(str(p) for p in own_threats["rush4_spots"][:5])
            lines.append(f"己方可形成冲四的点: {pts}")
        if own_threats["live3_spots"]:
            pts = " ".join(str(p) for p in own_threats["live3_spots"][:5])
            lines.append(f"己方可形成活三的点: {pts}")

        if len(lines) == 1:
            lines.append("当前无明显威胁，正常布局即可。")

        return "\n".join(lines)

    def _own_skill_section(self) -> str:
        skill = self.ctrl.current_player.skill
        if not skill:
            return ""
        return f"己方: {skill.skill_name}({skill.description})"

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
        return f"敌方: {skill.skill_name}({skill.description})"
