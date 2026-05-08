"""Minimax + Alpha-Beta 剪枝搜索 —— 为 AI 提供算法级决策支持"""

from __future__ import annotations
import time
from .pattern import extract_patterns, DIRECTIONS, BOARD_SIZE
from .evaluate import evaluate_board, score_position

INF = 10_000_000
WIN_SCORE = 1_000_000


def get_best_move(grid, ai_symbol, blocked=None, depth=2, time_limit=0.3):
    """Minimax + Alpha-Beta 搜索最佳落子

    Args:
        grid: 15x15 二维数组
        ai_symbol: AI 的棋子符号 ('X' 或 'O')
        blocked: 封锁位置集合
        depth: 搜索深度（默认2，越大越强但越慢）
        time_limit: 时间限制（秒），超时则返回当前最佳

    Returns:
        (x, y) 或 None
    """
    if blocked is None:
        blocked = set()

    opponent = 'O' if ai_symbol == 'X' else 'X'
    candidates = _get_candidates(grid, blocked)

    if not candidates:
        return None

    best_move = candidates[0]
    best_score = -INF
    alpha = -INF
    beta = INF
    start_time = time.time()

    # 候选排序：按快速评估降序（最大化剪枝效率）
    candidates.sort(
        key=lambda m: score_position(grid, m[0], m[1], ai_symbol, blocked)
        + score_position(grid, m[0], m[1], opponent, blocked),
        reverse=True,
    )

    for x, y in candidates:
        # 先检查是否直接获胜
        p = extract_patterns(grid, x, y, ai_symbol, blocked)
        if p["win"] > 0:
            return (x, y)

        grid[y][x] = ai_symbol
        score = _minimax(grid, depth - 1, alpha, beta, False,
                         ai_symbol, opponent, blocked, start_time, time_limit)
        grid[y][x] = ' '

        if score > best_score:
            best_score = score
            best_move = (x, y)
        alpha = max(alpha, score)

        if time.time() - start_time > time_limit and best_move is not None:
            break

    return best_move


def _minimax(grid, depth, alpha, beta, maximizing, ai_symbol, opponent,
             blocked, start_time, time_limit):
    """Alpha-Beta 剪枝递归搜索"""
    # 超时检查
    if time.time() - start_time > time_limit:
        return evaluate_board(grid, ai_symbol, blocked)

    # 终止条件
    if depth == 0:
        return evaluate_board(grid, ai_symbol, blocked)

    current_player = ai_symbol if maximizing else opponent

    # 检查当前玩家是否有立即获胜的落子
    candidates = _get_candidates(grid, blocked)
    if not candidates:
        return evaluate_board(grid, ai_symbol, blocked)

    if maximizing:
        max_eval = -INF
        for x, y in candidates:
            p = extract_patterns(grid, x, y, current_player, blocked)
            if p["win"] > 0:
                return WIN_SCORE * (depth + 1)

            grid[y][x] = current_player
            eval_score = _minimax(grid, depth - 1, alpha, beta, False,
                                  ai_symbol, opponent, blocked,
                                  start_time, time_limit)
            grid[y][x] = ' '

            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
            if time.time() - start_time > time_limit:
                break
        return max_eval
    else:
        min_eval = INF
        for x, y in candidates:
            p = extract_patterns(grid, x, y, current_player, blocked)
            if p["win"] > 0:
                return -WIN_SCORE * (depth + 1)

            grid[y][x] = current_player
            eval_score = _minimax(grid, depth - 1, alpha, beta, True,
                                  ai_symbol, opponent, blocked,
                                  start_time, time_limit)
            grid[y][x] = ' '

            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
            if time.time() - start_time > time_limit:
                break
        return min_eval


def _get_candidates(grid, blocked):
    """获取候选落子位置：已有棋子周围半径2格内的空位"""
    candidates = set()
    has_stones = False
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if grid[y][x] in ('X', 'O'):
                has_stones = True
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = x + dx, y + dy
                        if (0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE
                                and grid[ny][nx] in (' ', '.')
                                and (nx, ny) not in blocked):
                            candidates.add((nx, ny))
    if not has_stones:
        return [(7, 7)]
    return list(candidates)
