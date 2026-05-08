"""启发式评分引擎：棋型识别、位置评分、最佳落子决策"""

N = 15
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]

# (连子数, 开放端数) → 分数
PATTERN_SCORES = {
    (5, 0): 10_000_000,
    (5, 1): 10_000_000,
    (5, 2): 10_000_000,
    (4, 2): 1_000_000,
    (4, 1): 100_000,
    (3, 2): 50_000,
    (3, 1): 5_000,
    (2, 2): 1_000,
    (2, 1): 100,
    (1, 2): 50,
    (1, 1): 10,
}


def _count_in_direction(board, x, y, dx, dy, color):
    """从 (x+dx, y+dy) 开始沿 (dx,dy) 方向数连续同色棋子"""
    count = 0
    nx, ny = x + dx, y + dy
    while 0 <= nx < N and 0 <= ny < N and board[ny][nx] == color:
        count += 1
        nx += dx
        ny += dy
    return count


def _analyze_line(board, x, y, dx, dy, color):
    """分析经过 (x,y) 的某个方向上的棋型（假设 (x,y) 已放置 color）

    返回: (连子数, 开放端数)
    """
    forward = _count_in_direction(board, x, y, dx, dy, color)
    backward = _count_in_direction(board, x, y, -dx, -dy, color)
    total = 1 + forward + backward

    open_ends = 0
    # 检查前进方向的末端
    fx, fy = x + dx * (forward + 1), y + dy * (forward + 1)
    if 0 <= fx < N and 0 <= fy < N and board[fy][fx] == " ":
        open_ends += 1
    # 检查后退方向的末端
    bx, by = x - dx * (backward + 1), y - dy * (backward + 1)
    if 0 <= bx < N and 0 <= by < N and board[by][bx] == " ":
        open_ends += 1

    return total, open_ends


def evaluate_position(board, x, y, color):
    """评估在 (x,y) 放置 color 棋子后的总评分（四个方向之和）"""
    total = 0
    for dx, dy in DIRECTIONS:
        count, open_ends = _analyze_line(board, x, y, dx, dy, color)
        if count >= 5:
            return 10_000_000  # 直接获胜，提前返回
        score = PATTERN_SCORES.get((count, open_ends), 0)
        total += score
    return total


def is_empty(board):
    """检测棋盘是否为空"""
    for y in range(N):
        for x in range(N):
            if board[y][x] != " ":
                return False
    return True


def get_best_move(board, ai_color):
    """综合进攻与防守分，返回最佳落子坐标 (x, y)"""
    opponent = "X" if ai_color == "O" else "O"

    if is_empty(board):
        return (7, 7)  # 首步落天元

    candidates = []
    for y in range(N):
        for x in range(N):
            if board[y][x] != " ":
                continue

            attack = evaluate_position(board, x, y, ai_color)
            defense = evaluate_position(board, x, y, opponent)

            # 防守权重略低于进攻，避免过于保守
            score = attack + defense * 0.9
            candidates.append((score, x, y))

    if not candidates:
        return None

    candidates.sort(key=lambda t: t[0], reverse=True)
    return (candidates[0][1], candidates[0][2])
