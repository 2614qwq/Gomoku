"""五子棋核心数据模型

Board  —— 棋盘状态，含技能生成子的追踪
Player —— 玩家信息，绑定招式
Position —— 坐标
SkillResult —— 招式触发结果
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
import random

from .constants import BOARD_SIZE, EMPTY, BLACK, WHITE, DIRECTIONS, ADJACENT_4, DIAGONAL_4, ALL_8

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
        _grid: 15x15 字符网格，' ' / 'X' / 'O'
        _skill_stones: 由招式生成的棋子坐标集合，供五雷阵/绝户阵追踪
    """

    def __init__(self):
        self._grid: list[list[str]] = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self._skill_stones: set[tuple] = set()
        self._blocked_positions: set[tuple] = set()  # 困龙阵/梅花阵封锁的位置

    # ---- 基础访问 ----

    @property
    def grid(self) -> list[list[str]]:
        return self._grid

    def get(self, x: int, y: int) -> str:
        return self._grid[y][x]

    def is_empty(self, x: int, y: int) -> bool:
        return (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE
                and self._grid[y][x] == EMPTY
                and (x, y) not in self._blocked_positions)

    def is_valid(self, x: int, y: int) -> bool:
        return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

    # ---- 落子 / 移除 ----

    def place(self, x: int, y: int, color: str, is_skill: bool = False) -> bool:
        """落子。is_skill=True 表示该子由招式生成"""
        if not self.is_empty(x, y):
            return False
        self._grid[y][x] = color
        if is_skill:
            self._skill_stones.add((x, y))
        return True

    def remove(self, x: int, y: int):
        self._grid[y][x] = EMPTY
        self._skill_stones.discard((x, y))
        self._blocked_positions.discard((x, y))

    def block(self, x: int, y: int):
        """封锁一个空位（困龙阵/梅花阵）"""
        if self._grid[y][x] == EMPTY:
            self._blocked_positions.add((x, y))

    def unblock(self, x: int, y: int):
        self._blocked_positions.discard((x, y))

    def is_blocked(self, x: int, y: int) -> bool:
        return (x, y) in self._blocked_positions

    def clear_blocked(self):
        self._blocked_positions.clear()

    # ---- 技能子追踪 ----

    def is_skill_stone(self, x: int, y: int) -> bool:
        return (x, y) in self._skill_stones

    def count_skill_stones_of(self, color: str) -> int:
        return sum(1 for (sx, sy) in self._skill_stones if self._grid[sy][sx] == color)

    def get_skill_stone_positions_of(self, color: str) -> list[Position]:
        return [Position(sx, sy) for (sx, sy) in self._skill_stones
                if self._grid[sy][sx] == color]

    def remove_random_skill_stone_of(self, color: str) -> Optional[Position]:
        """随机移除指定颜色的一个技能生成子"""
        candidates = self.get_skill_stone_positions_of(color)
        if not candidates:
            return None
        pos = random.choice(candidates)
        self.remove(pos.x, pos.y)
        return pos

    # ---- 胜负判定 ----

    def check_win(self, color: str) -> bool:
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if self._grid[y][x] != color:
                    continue
                for dx, dy in DIRECTIONS:
                    cnt = 1
                    for s in range(1, 5):
                        nx, ny = x + dx * s, y + dy * s
                        if self.is_valid(nx, ny) and self._grid[ny][nx] == color:
                            cnt += 1
                        else:
                            break
                    if cnt >= 5:
                        return True
        return False

    def is_full(self) -> bool:
        return all(c != EMPTY for row in self._grid for c in row)

    # ---- 位置查询（供招式使用） ----

    def get_empty_positions(self) -> list[Position]:
        return [Position(x, y) for y in range(BOARD_SIZE) for x in range(BOARD_SIZE)
                if self._grid[y][x] == EMPTY and (x, y) not in self._blocked_positions]

    def get_edge_positions(self) -> list[Position]:
        """边角位置（距边缘1格以内）"""
        result = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if self._grid[y][x] != EMPTY and self._is_edge(x, y):
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

    def find_lines(self, color: str, length: int) -> list[list[Position]]:
        """查找指定颜色长度为 length 的连线，返回每条线的位置列表"""
        lines = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if self._grid[y][x] != color:
                    continue
                for dx, dy in DIRECTIONS:
                    # 只从线段起点记录（避免重复）
                    px, py = x - dx, y - dy
                    if self.is_valid(px, py) and self._grid[py][px] == color:
                        continue
                    line = [Position(x + dx * i, y + dy * i) for i in range(length)
                            if self.is_valid(x + dx * i, y + dy * i)
                            and self._grid[y + dy * i][x + dx * i] == color]
                    if len(line) == length:
                        lines.append(line)
        return lines

    def is_same_line(self, pos1: Position, pos2: Position) -> bool:
        """判断两个位置是否在同一直线（水平/垂直/对角线）"""
        dx = abs(pos1.x - pos2.x)
        dy = abs(pos1.y - pos2.y)
        return dx == 0 or dy == 0 or dx == dy

    def get_line_direction(self, pos1: Position, pos2: Position) -> Optional[tuple]:
        """返回两点所在直线的方向向量，不在同一直线返回 None"""
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
        """获取从pos沿direction方向上的空位"""
        result = []
        dx, dy = direction
        for step in range(1, BOARD_SIZE):
            nx, ny = pos.x + dx * step, pos.y + dy * step
            if not self.is_valid(nx, ny):
                break
            if self._grid[ny][nx] == EMPTY and (nx, ny) not in self._blocked_positions:
                result.append(Position(nx, ny))
        # 反向
        for step in range(1, BOARD_SIZE):
            nx, ny = pos.x - dx * step, pos.y - dy * step
            if not self.is_valid(nx, ny):
                break
            if self._grid[ny][nx] == EMPTY and (nx, ny) not in self._blocked_positions:
                result.append(Position(nx, ny))
        return result

    # ---- 重置 ----

    def reset(self):
        self._grid = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self._skill_stones.clear()
        self._blocked_positions.clear()
