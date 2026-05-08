"""GameInfoExtractor —— 从 GameController 提取 Agent 所需的文本报告"""

from ..board_codec import board_to_text


class GameInfoExtractor:
    """唯一直接访问 GameController 的类。生成 game_report 供所有 Agent 共用。"""

    def __init__(self, controller):
        self.ctrl = controller

    def build_game_report(self) -> str:
        sections = [
            self._turn_section(),
            self._board_section(),
            self._threat_section(),
            self._own_skill_section(),
            self._enemy_skill_section(),
            self._candidates_section(),
        ]
        return "\n\n".join(filter(None, sections))

    # ---- 各信息段落 ----

    def _turn_section(self) -> str:
        p = self.ctrl.current_player
        return (f"【回合信息】\n"
                f"当前回合: 第{self.ctrl.turn_count}步\n"
                f"轮到: {p.name}({p.color})\n"
                f"对手: {self.ctrl.opponent_player.name}({self.ctrl.opponent_player.color})")

    def _board_section(self) -> str:
        return "【棋盘状态】\n" + board_to_text(self.ctrl.board.grid)

    def _threat_section(self) -> str:
        lines = []
        my_color = self.ctrl.current_player.color
        opp_color = self.ctrl.opponent_player.color

        for length, label in [(4, "四连(危险!)"), (3, "三连"), (2, "二连")]:
            my_lines = self.ctrl.board.find_lines(my_color, length)
            opp_lines = self.ctrl.board.find_lines(opp_color, length)
            if my_lines:
                lines.append(f"  己方{label}: {len(my_lines)}处")
            if opp_lines:
                lines.append(f"  对方{label}: {len(opp_lines)}处 — 共{sum(len(l) for l in opp_lines)}子")
                if length >= 3 and opp_lines:
                    for line in opp_lines[:3]:
                        pts = [f"({p.x},{p.y})" for p in line]
                        lines.append(f"    位置: {', '.join(pts)}")

        return "【威胁分析】\n" + ("\n".join(lines) if lines else "  无明显威胁")

    def _own_skill_section(self) -> str:
        skill = self.ctrl.current_player.skill
        if not skill:
            return ""
        type_str = "主动" if skill.skill_type.name == "ACTIVE" else "被动"
        can_use = ""
        if skill.skill_type.name == "ACTIVE":
            try:
                if skill.can_activate(self.ctrl.current_player,
                                     self.ctrl.board, self.ctrl.turn_count):
                    can_use = " 状态: ★ 可用!"
                else:
                    can_use = f" 状态: 冷却中 (当前第{self.ctrl.turn_count}步)"
            except Exception:
                pass
        return (f"【己方招式】\n"
                f"  名称: {skill.skill_name}\n"
                f"  类型: {type_str}\n"
                f"  描述: {skill.description}\n"
                f"{can_use}")

    def _enemy_skill_section(self) -> str:
        skill = self.ctrl.opponent_player.skill
        if not skill:
            return ""
        opp_color = self.ctrl.opponent_player.color
        type_str = "主动" if skill.skill_type.name == "ACTIVE" else "被动"

        skill_stones = self.ctrl.board.get_skill_stone_positions_of(opp_color)
        skill_count = len(skill_stones)
        stone_info = f"  敌方技能子: {skill_count}颗"
        if skill_stones:
            stone_info += f" 位置: {', '.join(f'({p.x},{p.y})' for p in skill_stones[:5])}"

        blocked = []
        for y in range(15):
            for x in range(15):
                if self.ctrl.board.is_blocked(x, y):
                    blocked.append(f"({x},{y})")
        block_info = f"  封锁位: {', '.join(blocked)}" if blocked else "  封锁位: 无"

        return (f"【敌方招式】\n"
                f"  名称: {skill.skill_name}\n"
                f"  类型: {type_str}\n"
                f"  描述: {skill.description}\n"
                f"{stone_info}\n"
                f"{block_info}")

    def _candidates_section(self) -> str:
        try:
            board = self.ctrl.board
            my_color = self.ctrl.current_player.color
            opp_color = self.ctrl.opponent_player.color
            scored = []
            for y in range(15):
                for x in range(15):
                    if board.is_empty(x, y):
                        score1 = self._quick_score(board, x, y, my_color)
                        score2 = self._quick_score(board, x, y, opp_color)
                        scored.append(((x, y), score1 + score2 * 0.9))
            scored.sort(key=lambda v: v[1], reverse=True)
            top = scored[:8]
            lines = [f"  ({x},{y}): score={s:.0f}" for (x, y), s in top]
            return "【Engine Top-8 候选】\n" + "\n".join(lines)
        except Exception:
            return ""

    def _quick_score(self, board, x, y, color) -> float:
        """对单点快速评分（简化版 engine）"""
        score = 0.0
        for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            cnt, opens = 1, 0
            for s in range(1, 5):
                nx, ny = x + dx * s, y + dy * s
                if 0 <= nx < 15 and 0 <= ny < 15 and board.get(nx, ny) == color:
                    cnt += 1
                else:
                    if 0 <= nx < 15 and 0 <= ny < 15 and board.get(nx, ny) == ' ':
                        opens += 1
                    break
            for s in range(1, 5):
                nx, ny = x - dx * s, y - dy * s
                if 0 <= nx < 15 and 0 <= ny < 15 and board.get(nx, ny) == color:
                    cnt += 1
                else:
                    if 0 <= nx < 15 and 0 <= ny < 15 and board.get(nx, ny) == ' ':
                        opens += 1
                    break
            if cnt >= 5:
                score += 10000000
            elif cnt == 4 and opens == 2:
                score += 1000000
            elif cnt == 4 and opens == 1:
                score += 100000
            elif cnt == 3 and opens == 2:
                score += 50000
            elif cnt == 3 and opens == 1:
                score += 5000
            elif cnt == 2 and opens == 2:
                score += 1000
            elif cnt == 2 and opens == 1:
                score += 100
        return score
