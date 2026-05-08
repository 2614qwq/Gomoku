"""招式显示与激活窗口

SkillWindow —— 显示单个玩家的招式信息、主动招式激活按钮、AI提示按钮、消息日志
"""
from __future__ import annotations
import tkinter as tk
from typing import Optional, TYPE_CHECKING

from ..skills import SkillType, Skill

if TYPE_CHECKING:
    from ..core.models import Player


class SkillWindow(tk.Toplevel):
    """单个玩家的招式面板窗口

    布局:
        ┌─────────────────────────┐
        │    ⚡ [颜色]招式面板      │
        ├─────────────────────────┤
        │ 招式: XXX (主动/被动)     │
        │ 描述...                  │
        │ [使用招式] [AI提示]      │
        ├─────────────────────────┤
        │ 消息日志                 │
        └─────────────────────────┘
    """

    def __init__(self, parent: tk.Tk, player_name: str, player_color: str,
                 is_human: bool = True):
        super().__init__(parent)
        color_cn = "黑棋" if player_color == 'X' else "白棋"
        self.title(f"{color_cn}招式面板")
        self.geometry("320x400")
        self.resizable(False, False)
        self.transient(parent)

        self._player_name = player_name
        self._player_color = player_color
        self._is_human = is_human

        # 回调
        self._on_activate_callback = None
        self._on_ai_hint_callback = None

        # ---- 标题 ----
        title_frame = tk.Frame(self, bg='#3C1F0A')
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text=f"⚡ {color_cn}招式面板", font=('SimHei', 14, 'bold'),
                 bg='#3C1F0A', fg='#DCB35C', pady=8).pack()

        # ---- 招式区域 ----
        self._skill_frame = tk.LabelFrame(self, text="当前招式", font=('SimHei', 11),
                                          fg='#3C1F0A', padx=8, pady=8)
        self._skill_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self._skill_name_label = tk.Label(self._skill_frame, text="",
                                          font=('SimHei', 12, 'bold'), fg='#3C1F0A')
        self._skill_name_label.pack(anchor=tk.W)

        self._skill_desc_label = tk.Label(self._skill_frame, text="",
                                          font=('SimHei', 10), fg='#666666',
                                          wraplength=280, justify=tk.LEFT)
        self._skill_desc_label.pack(anchor=tk.W, pady=(2, 6))

        # 按钮框架
        btn_frame = tk.Frame(self._skill_frame)
        btn_frame.pack(fill=tk.X)

        self._activate_btn = tk.Button(btn_frame, text="使用招式",
                                       font=('SimHei', 12, 'bold'),
                                       bg='#DCB35C', fg='#3C1F0A',
                                       activebackground='#E8C86A',
                                       state=tk.DISABLED,
                                       command=self._on_activate_click)
        self._activate_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self._ai_hint_btn = tk.Button(btn_frame, text="AI提示",
                                      font=('SimHei', 10),
                                      bg='#6B8E6B', fg='white',
                                      activebackground='#8DAE8D',
                                      state=tk.DISABLED,
                                      command=self._on_ai_hint_click)
        self._ai_hint_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        # ---- 消息日志 ----
        log_frame = tk.LabelFrame(self, text="消息日志", font=('SimHei', 11),
                                  fg='#3C1F0A', padx=8, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._log_text = tk.Text(log_frame, font=('SimHei', 9), fg='#3C1F0A',
                                 bg='#FDF5E6', height=8, wrap=tk.WORD,
                                 state=tk.DISABLED)
        self._log_text.pack(fill=tk.BOTH, expand=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- 回调设置 ----

    def set_on_activate(self, callback):
        """设置"使用招式"按钮回调"""
        self._on_activate_callback = callback

    def set_on_ai_hint(self, callback):
        """设置"AI提示"按钮回调"""
        self._on_ai_hint_callback = callback

    # ---- 内部事件 ----

    def _on_activate_click(self):
        if self._on_activate_callback:
            self._on_activate_callback()

    def _on_ai_hint_click(self):
        if self._on_ai_hint_callback:
            self._on_ai_hint_callback()

    def _on_close(self):
        pass  # 由 game_window 统一管理销毁

    # ---- 公开接口 ----

    def update_state(self, player: Player, skill_active: bool,
                     is_current_turn: bool, ai_enabled: bool, message: str = ""):
        """更新面板状态

        Args:
            player: 该窗口对应的玩家
            skill_active: 主动招式是否可激活
            is_current_turn: 当前是否该玩家的回合
            ai_enabled: AI 是否启用
            message: 可选的状态消息
        """
        skill = player.skill

        # 招式信息
        if skill:
            type_str = "主动" if skill.skill_type == SkillType.ACTIVE else "被动"
            self._skill_name_label.config(
                text=f"{player.name}: {skill.skill_name} ({type_str})")
            self._skill_desc_label.config(text=skill.description)
        else:
            self._skill_name_label.config(text=f"{player.name}: 无招式")
            self._skill_desc_label.config(text="")

        # 激活按钮：人类玩家 + 当前回合 + 有主动技能 + 可用
        if (self._is_human and is_current_turn
                and skill and skill.skill_type == SkillType.ACTIVE
                and skill_active):
            self._activate_btn.config(state=tk.NORMAL)
        else:
            self._activate_btn.config(state=tk.DISABLED)

        # AI提示按钮：人类玩家 + AI启用 + 当前回合
        if self._is_human and ai_enabled and is_current_turn:
            self._ai_hint_btn.config(state=tk.NORMAL)
        else:
            self._ai_hint_btn.config(state=tk.DISABLED)

        # 消息日志
        if message:
            self._log_text.config(state=tk.NORMAL)
            self._log_text.insert(tk.END, message + "\n")
            self._log_text.see(tk.END)
            self._log_text.config(state=tk.DISABLED)

    def show_message(self, message: str):
        """追加消息到日志"""
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, message + "\n")
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def highlight_skill_active(self, player_name: str, message: str):
        """突出显示招式触发信息"""
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, f">>> {player_name}: {message}\n")
        self._log_text.see(tk.END)
        self._log_text.insert(tk.END, "-" * 30 + "\n")
        self._log_text.config(state=tk.DISABLED)
