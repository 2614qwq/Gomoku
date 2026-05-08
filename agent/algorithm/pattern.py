"""五子棋棋型检测 —— 基于优化策略的规则转算法实现

核心逻辑：
  - 四个方向双向计数，遇到边界/对方子/空位/封锁位立即停止
  - 端点状态记录：正/负方向第一个非己方格子是"空位"还是"被堵"
  - 连续子总数 + 两端空位数 → 棋型映射
"""

from __future__ import annotations

DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]  # 水平、垂直、主对角、副对角
BOARD_SIZE = 15


def extract_patterns(grid, x, y, player, blocked=None):
    """提取 (x,y) 落子后产生的棋型数量

    Args:
        grid: 15x15 二维数组, ' '/'.'=空, 'X'=黑, 'O'=白
        player: 当前落子方 ('X' 或 'O')
        blocked: 封锁位置集合 set of (x, y)

    Returns:
        dict: {"win": n, "live4": n, "rush4": n, "live3": n, "rush3": n, "live2": n}
    """
    if blocked is None:
        blocked = set()

    patterns = {"win": 0, "live4": 0, "rush4": 0, "live3": 0, "rush3": 0, "live2": 0}

    def _is_empty(_x, _y):
        return (0 <= _x < BOARD_SIZE and 0 <= _y < BOARD_SIZE
                and grid[_y][_x] in (' ', '.')
                and (_x, _y) not in blocked)

    def _is_player(_x, _y):
        return 0 <= _x < BOARD_SIZE and 0 <= _y < BOARD_SIZE and grid[_y][_x] == player

    for dx, dy in DIRECTIONS:
        # 正向计数
        count_pos = 0
        x1, y1 = x + dx, y + dy
        while _is_player(x1, y1):
            count_pos += 1
            x1 += dx
            y1 += dy
        pos_open = _is_empty(x1, y1)

        # 反向计数
        count_neg = 0
        x2, y2 = x - dx, y - dy
        while _is_player(x2, y2):
            count_neg += 1
            x2 -= dx
            y2 -= dy
        neg_open = _is_empty(x2, y2)

        total = count_pos + count_neg + 1

        # 棋型判定
        if total >= 5:
            patterns["win"] += 1
        elif total == 4:
            empty_ends = (1 if pos_open else 0) + (1 if neg_open else 0)
            if empty_ends == 2:
                patterns["live4"] += 1
            elif empty_ends == 1:
                patterns["rush4"] += 1
        elif total == 3:
            empty_ends = (1 if pos_open else 0) + (1 if neg_open else 0)
            if empty_ends == 2:
                patterns["live3"] += 1
            elif empty_ends == 1:
                patterns["rush3"] += 1
        elif total == 2:
            empty_ends = (1 if pos_open else 0) + (1 if neg_open else 0)
            if empty_ends == 2:
                patterns["live2"] += 1

    return patterns


def _empty_positions_near_stones(grid, blocked, radius=2):
    """获取已有棋子周围 radius 格内的空位候选列表"""
    candidates = set()
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if grid[y][x] in ('X', 'O'):
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        nx, ny = x + dx, y + dy
                        if (0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE
                                and grid[ny][nx] in (' ', '.')
                                and (nx, ny) not in blocked):
                            candidates.add((nx, ny))
    return list(candidates)


def find_immediate_win(grid, player, blocked=None):
    """找到当前玩家立即获胜的落子位置

    Returns:
        (x, y) 或 None
    """
    if blocked is None:
        blocked = set()
    candidates = _empty_positions_near_stones(grid, blocked, radius=1)
    for x, y in candidates:
        p = extract_patterns(grid, x, y, player, blocked)
        if p["win"] > 0:
            return (x, y)
    # 候选为空时全局搜索
    if not candidates:
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if grid[y][x] in (' ', '.') and (x, y) not in blocked:
                    p = extract_patterns(grid, x, y, player, blocked)
                    if p["win"] > 0:
                        return (x, y)
    return None


def find_must_block(grid, opponent, blocked=None):
    """找到必须封堵的对手获胜威胁位置（即对手的成五落点）

    Returns:
        (x, y) 或 None —— 对手下一手会赢的位置（也就是我方必须落子的位置）
    """
    return find_immediate_win(grid, opponent, blocked)


def find_double_threat_moves(grid, player, blocked=None):
    """找到能形成双重威胁（活三+活三 或 活三+冲四）的落子

    一手落下同时形成两个活三或一个冲四+活三，对手无法同时防守。

    Returns:
        list of (x, y)
    """
    if blocked is None:
        blocked = set()
    candidates = _empty_positions_near_stones(grid, blocked, radius=2)
    result = []
    for x, y in candidates:
        p = extract_patterns(grid, x, y, player, blocked)
        # 直接赢的不算（由 find_immediate_win 处理）
        if p["win"] > 0:
            continue
        # 双活三或活三+冲四都是必胜
        if p["live3"] >= 2:
            result.append((x, y))
        elif p["live3"] >= 1 and p["rush4"] >= 1:
            result.append((x, y))
        elif p["live4"] >= 1:
            result.append((x, y))
        elif p["rush4"] >= 2:
            result.append((x, y))
    return result


def find_existing_live3_blocks(grid, player, blocked=None):
    """找到对手已有活三的封堵位置。

    扫描棋盘上 player 已形成的活三（三子连线 + 两端空），
    返回所有可封堵的位置。

    为什么必须封堵活三：对手下一步在该线的任一端落子，活三变活四。
    活四两端皆空，堵一端对手赢另一端，无法防守。

    Returns:
        list of (x, y) 封堵位置（去重）
    """
    if blocked is None:
        blocked = set()

    blocks = set()
    visited = set()

    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if grid[y][x] != player:
                continue
            for dx, dy in DIRECTIONS:
                # 只从线段起点开始计数（前一个位置不是 player）
                px, py = x - dx, y - dy
                if 0 <= px < BOARD_SIZE and 0 <= py < BOARD_SIZE and grid[py][px] == player:
                    continue

                line_key = (x, y, dx, dy)
                if line_key in visited:
                    continue
                visited.add(line_key)

                # 正向计数连续同色子
                count = 1
                cx, cy = x + dx, y + dy
                while (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE
                       and grid[cy][cx] == player):
                    count += 1
                    cx += dx
                    cy += dy

                if count != 3:
                    continue

                # 两端状态：必须两端都空才是活三
                neg_x, neg_y = x - dx, y - dy
                neg_open = (0 <= neg_x < BOARD_SIZE and 0 <= neg_y < BOARD_SIZE
                            and grid[neg_y][neg_x] in (' ', '.')
                            and (neg_x, neg_y) not in blocked)
                pos_open = (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE
                            and grid[cy][cx] in (' ', '.')
                            and (cx, cy) not in blocked)

                if neg_open and pos_open:
                    blocks.add((neg_x, neg_y))
                    blocks.add((cx, cy))

    return list(blocks)


def scan_threats(grid, player, blocked=None):
    """扫描棋盘上某玩家所有的威胁

    Returns:
        dict: {
            "win_threats": [(x, y), ...],      # 对手下一手能赢的位置（必须堵）
            "double_threats": [(x, y), ...],    # 能形成双重威胁的落点
            "live4_spots": [(x, y), ...],       # 能形成活四的落点
            "rush4_spots": [(x, y), ...],       # 能形成冲四的落点
            "live3_spots": [(x, y), ...],       # 能形成活三的落点
        }
    """
    if blocked is None:
        blocked = set()
    threats = {
        "win_threats": [],
        "double_threats": [],
        "live4_spots": [],
        "rush4_spots": [],
        "live3_spots": [],
    }
    candidates = _empty_positions_near_stones(grid, blocked, radius=2)
    for x, y in candidates:
        p = extract_patterns(grid, x, y, player, blocked)
        if p["win"] > 0:
            threats["win_threats"].append((x, y))
        elif p["live4"] > 0:
            threats["live4_spots"].append((x, y))
        elif p["live3"] >= 2 or (p["live3"] >= 1 and p["rush4"] >= 1) or p["rush4"] >= 2:
            threats["double_threats"].append((x, y))
        elif p["rush4"] > 0:
            threats["rush4_spots"].append((x, y))
        elif p["live3"] > 0:
            threats["live3_spots"].append((x, y))
    return threats