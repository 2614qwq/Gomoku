"""五子棋核心数据模型

Board  —— 棋盘状态（int 网格：0=空 奇数=黑 偶数=白）
Player —— 玩家信息，绑定招式
Position —— 坐标
SkillResult —— 招式触发结果
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
import random

from .constants import (
    BOARD_SIZE, EMPTY, BLACK, WHITE, DIRECTIONS, ADJACENT_4, DIAGONAL_4, ALL_8,
    is_black, is_white, int_to_char,
)

if TYPE_CHECKING:
    from ..skills.base import Skill


@dataclass(frozen=True)
class Position:
    """棋盘坐标 (col=x, row=y)"""
    x: int
    y: int

    def __add__(self, other: tuple) -> Position:
        return Position(self.x + other[0], self.y + other[1])

    def is_valid(self) -> bool:
        return 0 <= self.x < BOARD_SIZE and 0 <= self.y < BOARD_SIZE

    def __repr__(self) -> str:
        return f"({self.x},{self.y})"


@dataclass
class SkillResult:
    """招式触发后产生的结果"""
    extra_stones: list[Position] = field(default_factory=list)
    removed_stones: list[Position] = field(default_factory=list)
    blocked_positions: list[Position] = field(default_factory=list)
    message: str = ""


@dataclass
class Player:
    """玩家信息"""
    color: str          # BLACK / WHITE
    name: str           # 黑棋 / 白棋
    skill: Optional[Skill] = None

    @property
    def display_color(self) -> str:
        return 'black' if self.color == BLACK else 'white'


class Board:
    """棋盘状态

    Attributes:
        _grid: 15x15 int 网格
               0 = 空，奇数(1,3,5...) = 黑棋，偶数(2,4,6...) = 白棋
        _move_count: 当前总落子数（= 最大序号，亦为下一手的序号）
        _blocked_positions: 临时封锁的空位集合
    """

    def __init__(self):
        self._grid: list[list[int]] = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self._move_count: int = 0
        self._blocked_positions: set[tuple] = set()

    # ---- 基础访问 ----

    @property
    def grid(self) -> list[list[int]]:
        return self._grid

    def get(self, x: int, y: int) -> int:
        """返回 int 值（0=空, 奇数=黑, 偶数=白）"""
        return self._grid[y][x]

    def get_color(self, x: int, y: int) -> str:
        """返回 X / O / ' ' """
        return int_to_char(self._grid[y][x])

    def get_move_number(self, x: int, y: int) -> int:
        """返回落子序号（0=空位）"""
        return self._grid[y][x]

    def is_black(self, x: int, y: int) -> bool:
        return is_black(self._grid[y][x])

    def is_white(self, x: int, y: int) -> bool:
        return is_white(self._grid[y][x])

    def is_empty(self, x: int, y: int) -> bool:
        return (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE
                and self._grid[y][x] == 0
                and (x, y) not in self._blocked_positions)

    def is_valid(self, x: int, y: int) -> bool:
        return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

    @property
    def move_count(self) -> int:
        return self._move_count

    # ---- 落子 / 移除 ----

    def place(self, x: int, y: int, color: str) -> int:
        """落子。返回新序号（也是 self._move_count）。

        Args:
            color: 'X'(黑) 或 'O'(白)
        Returns:
            新落子的序号（奇数=黑, 偶数=白）
        """
        if not self.is_empty(x, y):
            return 0
        self._move_count += 1
        self._grid[y][x] = self._move_count
        return self._move_count

    def remove(self, x: int, y: int):
        """移除 (x,y) 处的棋子（恢复为空位）"""
        self._grid[y][x] = 0
        self._blocked_positions.discard((x, y))

    def block(self, x: int, y: int):
        """封锁一个空位"""
        if self._grid[y][x] == 0:
            self._blocked_positions.add((x, y))

    def unblock(self, x: int, y: int):
        self._blocked_positions.discard((x, y))

    def is_blocked(self, x: int, y: int) -> bool:
        return (x, y) in self._blocked_positions

    def get_blocked_positions(self) -> list[Position]:
        return [Position(x, y) for (x, y) in self._blocked_positions]

    def clear_blocked(self):
        self._blocked_positions.clear()

    # ---- 胜负判定 ----

    def check_win(self, color: str) -> bool:
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if int_to_char(self._grid[y][x]) != color:
                    continue
                for dx, dy in DIRECTIONS:
                    cnt = 1
                    for s in range(1, 5):
                        nx, ny = x + dx * s, y + dy * s
                        if self.is_valid(nx, ny) and int_to_char(self._grid[ny][nx]) == color:
                            cnt += 1
                        else:
                            break
                    if cnt >= 5:
                        return True
        return False

    def check_win_int(self, black_turn: bool) -> bool:
        """int grid 版本：检测当前方是否五连获胜"""
        color = BLACK if black_turn else WHITE
        return self.check_win(color)

    def is_full(self) -> bool:
        return all(c != 0 for row in self._grid for c in row)

    # ---- 位置查询 ----

    def get_empty_positions(self) -> list[Position]:
        return [Position(x, y) for y in range(BOARD_SIZE) for x in range(BOARD_SIZE)
                if self._grid[y][x] == 0 and (x, y) not in self._blocked_positions]

    def get_all_stone_positions(self) -> list[Position]:
        """返回所有已落子位置"""
        return [Position(x, y) for y in range(BOARD_SIZE) for x in range(BOARD_SIZE)
                if self._grid[y][x] != 0]

    def get_stone_positions_of(self, color: str) -> list[Position]:
        """返回指定颜色的所有棋子位置"""
        result = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if int_to_char(self._grid[y][x]) == color:
                    result.append(Position(x, y))
        return result

    def get_edge_positions(self) -> list[Position]:
        """边角位置（距边缘1格以内）"""
        result = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if self._grid[y][x] != 0 and self._is_edge(x, y):
                    result.append(Position(x, y))
        return result

    def _is_edge(self, x: int, y: int) -> bool:
        return x <= 1 or x >= BOARD_SIZE - 2 or y <= 1 or y >= BOARD_SIZE - 2

    def get_neighbors(self, x: int, y: int, directions: list[tuple]) -> list[Position]:
        """获取指定方向上的邻居，仅返回合法空位"""
        result = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if self.is_empty(nx, ny):
                result.append(Position(nx, ny))
        return result

    def get_adjacent_empty(self, x: int, y: int) -> list[Position]:
        return self.get_neighbors(x, y, ADJACENT_4)

    def get_diagonal_empty(self, x: int, y: int) -> list[Position]:
        return self.get_neighbors(x, y, DIAGONAL_4)

    def get_all_adjacent_empty(self, x: int, y: int) -> list[Position]:
        """返回相邻8格内的所有空位"""
        result = []
        for dx, dy in ALL_8:
            nx, ny = x + dx, y + dy
            if self.is_empty(nx, ny):
                result.append(Position(nx, ny))
        return result

    def find_lines(self, color: str, length: int) -> list[list[Position]]:
        """查找指定颜色长度为 length 的连线，返回每条线的位置列表"""
        lines = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if int_to_char(self._grid[y][x]) != color:
                    continue
                for dx, dy in DIRECTIONS:
                    px, py = x - dx, y - dy
                    if self.is_valid(px, py) and int_to_char(self._grid[py][px]) == color:
                        continue
                    line = [Position(x + dx * i, y + dy * i) for i in range(length)
                            if self.is_valid(x + dx * i, y + dy * i)
                            and int_to_char(self._grid[y + dy * i][x + dx * i]) == color]
                    if len(line) == length:
                        lines.append(line)
        return lines

    def is_same_line(self, pos1: Position, pos2: Position) -> bool:
        dx = abs(pos1.x - pos2.x)
        dy = abs(pos1.y - pos2.y)
        return dx == 0 or dy == 0 or dx == dy

    def get_line_direction(self, pos1: Position, pos2: Position) -> Optional[tuple]:
        dx = pos2.x - pos1.x
        dy = pos2.y - pos1.y
        if dx == 0 and dy == 0:
            return None
        if dx == 0:
            return (0, 1 if dy > 0 else -1)
        if dy == 0:
            return (1 if dx > 0 else -1, 0)
        if abs(dx) == abs(dy):
            return (1 if dx > 0 else -1, 1 if dy > 0 else -1)
        return None

    def get_empty_on_line(self, pos: Position, direction: tuple) -> list[Position]:
        result = []
        dx, dy = direction
        for step in range(1, BOARD_SIZE):
            nx, ny = pos.x + dx * step, pos.y + dy * step
            if not self.is_valid(nx, ny):
                break
            if self._grid[ny][nx] == 0 and (nx, ny) not in self._blocked_positions:
                result.append(Position(nx, ny))
        for step in range(1, BOARD_SIZE):
            nx, ny = pos.x - dx * step, pos.y - dy * step
            if not self.is_valid(nx, ny):
                break
            if self._grid[ny][nx] == 0 and (nx, ny) not in self._blocked_positions:
                result.append(Position(nx, ny))
        return result

    # ---- 落子序列（供 Agent 使用） ----

    def get_move_sequence(self) -> list[tuple[int, int, int]]:
        """返回按序号排序的落子序列 [(x, y, 序号), ...]"""
        entries = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                v = self._grid[y][x]
                if v:
                    entries.append((x, y, v))
        entries.sort(key=lambda e: e[2])
        return entries

    # ---- 重置 ----

    def reset(self):
        self._grid = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self._move_count = 0
        self._blocked_positions.clear()
