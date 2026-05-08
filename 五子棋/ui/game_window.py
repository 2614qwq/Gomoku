"""五子棋 GUI 主程序（招式版 + 人机对战 + 双窗口 + AI辅助 + 后台线程）"""

from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from typing import Optional
import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from ..core.constants import (
        BOARD_SIZE, CELL_SIZE, MARGIN, STONE_RADIUS,
        BOARD_BG, LINE_COLOR, TEXT_COLOR,
        BLACK, WHITE, EMPTY, STAR_POINTS,
        WINDOW_WIDTH, WINDOW_HEIGHT,
    )
    from ..core.controller import GameController, GameState
    from .skill_window import SkillWindow
except ImportError:
    from core.constants import (  # type: ignore
        BOARD_SIZE, CELL_SIZE, MARGIN, STONE_RADIUS,
        BOARD_BG, LINE_COLOR, TEXT_COLOR,
        BLACK, WHITE, EMPTY, STAR_POINTS,
        WINDOW_WIDTH, WINDOW_HEIGHT,
    )
    from core.controller import GameController, GameState  # type: ignore
    from ui.skill_window import SkillWindow  # type: ignore

from agent.logger import get_logger

_log = get_logger("game_window")


class GomokuGUI:
    """五子棋 GUI 主类"""

    def __init__(self):
        self._controller = GameController()
        self._root = tk.Tk()
        self._root.title("五子棋 —— 万宁招式·多智能体版")
        self._cv = tk.Canvas(self._root, width=WINDOW_WIDTH + 20,
                             height=WINDOW_HEIGHT + 40, bg=BOARD_BG)
        self._cv.pack()
        self._skill_window_black: Optional[SkillWindow] = None
        self._skill_window_white: Optional[SkillWindow] = None
        self._ai_pending = False
        self._thinking_dots = 0

        self._cv.bind('<Button-1>', self._on_click)
        self._root.protocol("WM_DELETE_WINDOW", self._on_exit)

        self._controller.on_state_changed = self._on_state_changed
        self._controller.on_skill_triggered = self._on_skill_triggered
        self._controller.on_game_over = self._on_game_over

        _log.info("GUI 初始化完成")
        self._root.after(100, self._show_mode_selection)

    def run(self):
        self._root.mainloop()

    # ==================== 模式选择 ====================

    def _show_mode_selection(self):
        dlg = tk.Toplevel(self._root)
        dlg.title("选择游戏模式")
        dlg.geometry("320x260")
        dlg.resizable(False, False)
        dlg.transient(self._root)
        dlg.grab_set()

        tk.Label(dlg, text="五子棋 —— 万宁招式·多智能体版",
                 font=('SimHei', 13)).pack(pady=12)
        tk.Label(dlg, text="每局双方随机抽取一个招式",
                 font=('SimHei', 10), fg='#666666').pack()

        btn_font = ('SimHei', 11)

        def start(mode, enable_ai=False):
            self._controller.game_mode = mode
            dlg.destroy()
            self._start_new_game(enable_ai)

        tk.Button(dlg, text="双人对战", width=22, font=btn_font,
                  command=lambda: start(0, False)).pack(pady=4)
        tk.Button(dlg, text="人机对战（执黑·先手）", width=22, font=btn_font,
                  command=lambda: start(1, True)).pack(pady=4)
        tk.Button(dlg, text="人机对战（执白·后手）", width=22, font=btn_font,
                  command=lambda: start(2, True)).pack(pady=4)
        tk.Button(dlg, text="AI vs AI（观战模式）", width=22, font=btn_font,
                  command=lambda: start(3, True)).pack(pady=4)

    def _start_new_game(self, enable_ai: bool = False):
        self._controller.start_new_game()
        self._ai_pending = False
        self._thinking_dots = 0

        if enable_ai:
            self._controller.enable_ai()
            _log.info(f"AI 模式启用, mode={self._controller.game_mode}")
        else:
            self._controller.disable_ai()
            _log.info("双人模式")

        self._open_skill_windows()
        self._draw_board()

        # AI 先手
        if enable_ai and self._controller.game_mode in (2, 3):
            _log.info("AI 先手，准备落子")
            self._root.after(500, self._trigger_ai_move)

    # ==================== AI 逻辑 ====================

    def _is_ai_turn(self) -> bool:
        if not self._controller.ai_enabled:
            return False
        mode = self._controller.game_mode
        player_color = self._controller.current_player.color
        if mode == 1:
            return player_color == WHITE
        elif mode == 2:
            return player_color == BLACK
        elif mode == 3:
            return True
        return False

    def _is_human_player(self, color: str) -> bool:
        mode = self._controller.game_mode
        if mode == 0:
            return True
        elif mode == 1:
            return color == BLACK
        elif mode == 2:
            return color == WHITE
        elif mode == 3:
            return False
        return True

    def _trigger_ai_move(self):
        """在后台线程中触发 AI 落子，主线程通过轮询获取结果"""
        if self._controller.is_game_over():
            return
        if not self._is_ai_turn():
            return
        if self._ai_pending:
            return

        self._ai_pending = True
        self._thinking_dots = 0
        self._draw_board()
        self._root.update()

        _log.info(f"AI 开始思考 (turn={self._controller.turn_count})")

        # 后台线程执行 AI 推理
        ai_result_holder = {"data": None, "error": None}

        def run_ai():
            try:
                ai_result_holder["data"] = self._controller.trigger_ai_move()
            except Exception as e:
                _log.error(f"AI 线程异常: {e}")
                ai_result_holder["error"] = e

        thread = threading.Thread(target=run_ai, daemon=True)
        thread.start()

        # 启动轮询
        self._root.after(100, self._poll_ai_result, ai_result_holder)

    def _poll_ai_result(self, holder: dict):
        """主线程轮询 AI 结果，更新思考动画"""
        if holder["error"] is not None:
            _log.error(f"AI 错误: {holder['error']}")
            self._ai_pending = False
            self._draw_board()
            self._refresh_skill_windows()
            return

        if holder["data"] is None:
            # AI 仍在思考，更新动画
            self._thinking_dots = (self._thinking_dots + 1) % 4
            self._draw_thinking_indicator()
            self._root.after(100, self._poll_ai_result, holder)
            return

        # AI 完成
        result_data = holder["data"]
        self._ai_pending = False

        _log.info(f"AI 落子完成: {self._controller._last_move_pos}")

        # 在主线程处理分析结果
        if result_data and result_data.get("analysis"):
            self._on_ai_analysis(result_data["analysis"])

        self._draw_board()
        self._refresh_skill_windows()

        result = result_data.get("result") if result_data else None
        if result:
            _log.info(f"游戏结束: {result}")
            messagebox.showinfo("游戏结束", result)
            self._show_message_to_both(f"=== {result} ===")
        elif self._is_ai_turn():
            # AI vs AI: 继续下一步
            self._root.after(200, self._trigger_ai_move)

    def _draw_thinking_indicator(self):
        """在棋盘上绘制思考中动画"""
        if not self._ai_pending:
            return
        self._draw_board()
        dots = "." * (self._thinking_dots + 1)
        player = self._controller.current_player
        self._cv.create_text(
            WINDOW_WIDTH // 2 + 10, WINDOW_HEIGHT - 10,
            text=f"AI 思考中{dots}",
            font=('SimHei', 12), fill='#CC6600')

    def _on_ai_analysis(self, analysis: dict):
        """AI 分析结果回调 —— 在主线程执行，安全操作 UI"""
        current_color = self._controller.current_player.color
        window = self._get_window_for(current_color)

        if window:
            reason = analysis.get("reason", "")
            summaries = analysis.get("summaries", {})
            for role, summary in summaries.items():
                if summary:
                    window.highlight_skill_active(
                        f"AI-{role}", str(summary)[:80])
            if reason:
                window.show_message(f"AI 决策: {reason[:120]}")

    def _request_ai_hint(self, player_color: str):
        """为人类玩家请求 AI 提示（后台线程执行）"""
        if self._ai_pending:
            return
        if self._controller.current_player.color != player_color:
            return
        if not self._controller.ai_enabled:
            return

        window = self._get_window_for(player_color)
        if window:
            window.show_message("🤖 AI 正在分析局势...")
        self._root.update()

        hint_holder = {"data": None, "error": None}

        def run_hint():
            try:
                hint_holder["data"] = self._controller.request_ai_hint()
            except Exception as e:
                hint_holder["error"] = e

        thread = threading.Thread(target=run_hint, daemon=True)
        thread.start()

        def poll_hint():
            if hint_holder["error"] is not None:
                if window:
                    window.show_message(f"AI 提示请求失败: {hint_holder['error']}")
                return
            if hint_holder["data"] is None:
                self._root.after(100, poll_hint)
                return

            hint = hint_holder["data"]
            if hint is None or window is None:
                return

            move_x, move_y = hint["move"]
            window.show_message("=" * 40)
            window.show_message("🤖 AI 提示（仅供参考，请自行决策）:")
            window.show_message(f"  建议落子: ({move_x}, {move_y})")
            window.show_message(f"  分析理由: {hint['reason'][:150]}")
            summaries = hint.get("summaries", {})
            if summaries:
                window.show_message("  智能体意见:")
                role_names = {
                    "tactical": "战术官", "defense": "防守官",
                    "devil": "反对官", "chief": "总策划官",
                }
                for role, summary in summaries.items():
                    if summary:
                        role_cn = role_names.get(role, role)
                        window.show_message(f"    [{role_cn}]: {str(summary)[:100]}")
            window.show_message("=" * 40)

        self._root.after(100, poll_hint)

    # ==================== 招式窗口 ====================

    def _open_skill_windows(self):
        if self._skill_window_black:
            self._skill_window_black.destroy()
        if self._skill_window_white:
            self._skill_window_white.destroy()

        black_human = self._is_human_player(BLACK)
        white_human = self._is_human_player(WHITE)

        self._skill_window_black = SkillWindow(
            self._root, "黑棋", BLACK, is_human=black_human)
        self._skill_window_white = SkillWindow(
            self._root, "白棋", WHITE, is_human=white_human)

        self._skill_window_black.set_on_activate(self._on_skill_activate)
        self._skill_window_white.set_on_activate(self._on_skill_activate)

        if black_human:
            self._skill_window_black.set_on_ai_hint(
                lambda: self._request_ai_hint(BLACK))
        if white_human:
            self._skill_window_white.set_on_ai_hint(
                lambda: self._request_ai_hint(WHITE))

        self._root.update_idletasks()
        root_x = self._root.winfo_x()
        root_y = self._root.winfo_y()
        self._skill_window_black.geometry(f"+{max(0, root_x - 330)}+{root_y}")
        self._skill_window_white.geometry(f"+{root_x + WINDOW_WIDTH + 30}+{root_y}")

        self._refresh_skill_windows()

    def _get_window_for(self, color: str) -> Optional[SkillWindow]:
        if color == BLACK:
            return self._skill_window_black
        elif color == WHITE:
            return self._skill_window_white
        return None

    def _show_message_to_both(self, message: str):
        if self._skill_window_black:
            self._skill_window_black.show_message(message)
        if self._skill_window_white:
            self._skill_window_white.show_message(message)

    def _refresh_skill_windows(self):
        info = self._controller.get_current_skill_info()
        current_player = info['current_player']
        is_black_turn = current_player.color == BLACK
        ai_enabled = self._controller.ai_enabled

        if self._skill_window_black:
            self._skill_window_black.update_state(
                player=self._controller.black_player,
                skill_active=(info['skill_active']
                              and is_black_turn
                              and not self._ai_pending),
                is_current_turn=is_black_turn,
                ai_enabled=ai_enabled,
            )

        if self._skill_window_white:
            self._skill_window_white.update_state(
                player=self._controller.white_player,
                skill_active=(info['skill_active']
                              and not is_black_turn
                              and not self._ai_pending),
                is_current_turn=not is_black_turn,
                ai_enabled=ai_enabled,
            )

    def _on_skill_activate(self):
        if self._controller.is_skill_targeting():
            return
        error = self._controller.activate_skill()
        if error:
            window = self._get_window_for(
                self._controller.current_player.color)
            if window:
                window.show_message(error)
        else:
            if self._controller.is_skill_targeting():
                window = self._get_window_for(
                    self._controller.current_player.color)
                if window:
                    window.show_message("请在棋盘上点击选择招式目标位置")
            self._draw_board()
            self._refresh_skill_windows()

    # ==================== 棋盘绘制 ====================

    def _draw_board(self):
        self._cv.delete('all')
        board = self._controller.board

        for i in range(BOARD_SIZE):
            self._cv.create_line(MARGIN, MARGIN + i * CELL_SIZE,
                                 MARGIN + (BOARD_SIZE - 1) * CELL_SIZE,
                                 MARGIN + i * CELL_SIZE,
                                 fill=LINE_COLOR, width=2)
            self._cv.create_line(MARGIN + i * CELL_SIZE, MARGIN,
                                 MARGIN + i * CELL_SIZE,
                                 MARGIN + (BOARD_SIZE - 1) * CELL_SIZE,
                                 fill=LINE_COLOR, width=2)

        for px, py in STAR_POINTS:
            cx, cy = MARGIN + px * CELL_SIZE, MARGIN + py * CELL_SIZE
            self._cv.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=LINE_COLOR)

        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                stone = board.get(x, y)
                if stone == EMPTY:
                    continue
                cx, cy = MARGIN + x * CELL_SIZE, MARGIN + y * CELL_SIZE
                fill_color = 'black' if stone == BLACK else 'white'
                outline_color = '#CC4444' if board.is_skill_stone(x, y) else 'gray'
                self._cv.create_oval(cx - STONE_RADIUS, cy - STONE_RADIUS,
                                     cx + STONE_RADIUS, cy + STONE_RADIUS,
                                     fill=fill_color, outline=outline_color, width=2)

        # 绘制被封锁的位置（梅花阵花苞 / 困龙阵封锁）
        BUD_RADIUS = STONE_RADIUS - 2
        BUD_FILL = '#FFB7C5'       # 浅粉色花瓣
        BUD_OUTLINE = '#E75480'    # 深粉色轮廓
        for pos in board.get_blocked_positions():
            cx, cy = MARGIN + pos.x * CELL_SIZE, MARGIN + pos.y * CELL_SIZE
            # 花苞主体
            self._cv.create_oval(cx - BUD_RADIUS, cy - BUD_RADIUS,
                                 cx + BUD_RADIUS, cy + BUD_RADIUS,
                                 fill=BUD_FILL, outline=BUD_OUTLINE, width=2)
            # 花苞中心小点
            self._cv.create_oval(cx - 3, cy - 3, cx + 3, cy + 3,
                                 fill=BUD_OUTLINE, outline='')

        if not self._controller.is_game_over():
            player = self._controller.current_player
            mode = self._controller.game_mode

            if self._ai_pending:
                dots = "." * (self._thinking_dots + 1)
                status = f"AI 思考中{dots} ({player.name})"
            elif mode == 0:
                status = f"当前回合：{player.name}"
            elif mode == 1:
                status = f"当前回合：{player.name}" + (
                    "（你的回合）" if player.color == BLACK else "（AI 思考中…）")
            elif mode == 2:
                status = f"当前回合：{player.name}" + (
                    "（你的回合）" if player.color == WHITE else "（AI 思考中…）")
            elif mode == 3:
                status = f"AI vs AI — {player.name} 思考中"
            else:
                status = f"当前回合：{player.name}"

            self._cv.create_text(WINDOW_WIDTH // 2 + 10, WINDOW_HEIGHT + 20,
                                 text=status, font=('SimHei', 14), fill=TEXT_COLOR)

        if self._controller.is_skill_targeting():
            self._cv.create_text(WINDOW_WIDTH // 2 + 10, WINDOW_HEIGHT - 10,
                                 text=">>> 点击棋盘选择招式目标 <<<",
                                 font=('SimHei', 12, 'bold'), fill='#CC0000')

    # ==================== 事件处理 ====================

    def _on_click(self, ev):
        if self._controller.is_game_over():
            return
        if self._ai_pending:
            return
        if self._is_ai_turn():
            return

        col = round((ev.x - MARGIN) / CELL_SIZE)
        row = round((ev.y - MARGIN) / CELL_SIZE)

        if not (0 <= col < BOARD_SIZE and 0 <= row < BOARD_SIZE):
            return

        result = self._controller.handle_click(col, row)
        _log.debug(f"人类落子: ({col},{row}), turn={self._controller.turn_count}, "
                   f"result={result}")

        self._draw_board()
        self._refresh_skill_windows()

        if result:
            messagebox.showinfo("游戏结束", result)
            self._show_message_to_both(f"=== {result} ===")
            return

        # 人类落子后触发 AI
        if self._controller.ai_enabled and not self._controller.is_game_over():
            self._root.after(200, self._trigger_ai_move)

    def _on_state_changed(self):
        self._refresh_skill_windows()

    def _on_skill_triggered(self, player_name: str, message: str):
        _log.info(f"招式触发 | {player_name}: {message}")
        if player_name == "黑棋" and self._skill_window_black:
            self._skill_window_black.highlight_skill_active(player_name, message)
        elif player_name == "白棋" and self._skill_window_white:
            self._skill_window_white.highlight_skill_active(player_name, message)
        if player_name == "黑棋" and self._skill_window_white:
            self._skill_window_white.show_message(f"[对手] {player_name}: {message}")
        elif player_name == "白棋" and self._skill_window_black:
            self._skill_window_black.show_message(f"[对手] {player_name}: {message}")

    def _on_game_over(self, result_message: str):
        _log.info(f"游戏结束: {result_message}")
        self._draw_board()
        self._show_message_to_both(f"=== {result_message} ===")

    def _on_exit(self):
        _log.info("GUI 关闭")
        if self._skill_window_black:
            self._skill_window_black.destroy()
        if self._skill_window_white:
            self._skill_window_white.destroy()
        self._root.destroy()


if __name__ == '__main__':
    app = GomokuGUI()
    app.run()
