"""五子棋评估函数 —— 将棋型转化为分数，供搜索算法使用

grid 为 int 网格: 0=空, 奇数=黑(X), 偶数=白(O)
"""

from __future__ import annotations
from .pattern import extract_patterns, _is_own, DIRECTIONS, BOARD_SIZE

# 基础权重
WEIGHTS = {
    "win": 1000000,
    "live4": 50000,
    "rush4": 10000,
    "live3": 5000,
    "rush3": 500,
    "live2": 100,
}


def score_position(grid, x, y, player, blocked=None):
    """评估在 (x,y) 落子对 player 的价值（只看该点产生的棋型）

    Returns:
        int: 分数
    """
    p = extract_patterns(grid, x, y, player, blocked)
    score = 0
    for key, w in WEIGHTS.items():
        score += p.get(key, 0) * w
    return score


def evaluate_board(grid, ai_symbol, blocked=None):
    """评估整个棋盘对 AI 的优劣

    得分 = AI进攻分 - 对手进攻分 * 防守系数

    Returns:
        int: 正数对AI有利，负数对对手有利
    """
    opponent = 'O' if ai_symbol == 'X' else 'X'
    ai_score = _scan_all_patterns(grid, ai_symbol, blocked)
    opp_score = _scan_all_patterns(grid, opponent, blocked)
    return ai_score - opp_score * 0.9


def _scan_all_patterns(grid, player, blocked=None):
    """扫描棋盘上某玩家所有已形成的棋型总分

    逐行扫描，对每个 player 的棋子检查其所在方向上的连续棋型。
    只从线段起点计数，避免重复。
    """
    if blocked is None:
        blocked = set()
    total = 0
    visited = set()

    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if not _is_own(grid[y][x], player):
                continue
            for dx, dy in DIRECTIONS:
                line_key = (x, y, dx, dy)
                if line_key in visited:
                    continue

                px, py = x - dx, y - dy
                if 0 <= px < BOARD_SIZE and 0 <= py < BOARD_SIZE and _is_own(grid[py][px], player):
                    continue

                count = 1
                cx, cy = x + dx, y + dy
                while (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE
                       and _is_own(grid[cy][cx], player)):
                    count += 1
                    visited.add((cx, cy, dx, dy))
                    cx += dx
                    cy += dy

                pos_open = _is_empty(grid, cx, cy, blocked)
                px2, py2 = x - dx, y - dy
                neg_open = _is_empty(grid, px2, py2, blocked)

                if count >= 5:
                    total += WEIGHTS["win"]
                elif count == 4:
                    empty_ends = (1 if pos_open else 0) + (1 if neg_open else 0)
                    if empty_ends == 2:
                        total += WEIGHTS["live4"]
                    elif empty_ends == 1:
                        total += WEIGHTS["rush4"]
                elif count == 3:
                    empty_ends = (1 if pos_open else 0) + (1 if neg_open else 0)
                    if empty_ends == 2:
                        total += WEIGHTS["live3"]
                    elif empty_ends == 1:
                        total += WEIGHTS["rush3"]
                elif count == 2:
                    empty_ends = (1 if pos_open else 0) + (1 if neg_open else 0)
                    if empty_ends == 2:
                        total += WEIGHTS["live2"]

                visited.add(line_key)

    return total


def _is_empty(grid, x, y, blocked):
    if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
        return False
    if (x, y) in blocked:
        return False
    if grid[y][x] != 0:
        return False
    return True
