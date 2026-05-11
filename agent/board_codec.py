"""棋盘状态编解码：int 网格 ↔ 文本格式 互转

棋盘内部使用 int 网格:
  0    = 空位
  奇数 = 黑棋(X)
  偶数 = 白棋(O)

对外（LLM / UI）保持 X/O/* 文本 + 落子序列双轨输出。
"""

N = 15


def _is_black(v: int) -> bool:
    return v > 0 and v % 2 == 1


def _is_white(v: int) -> bool:
    return v > 0 and v % 2 == 0


def board_to_text(board, blocked=None):
    """将棋盘二维数组转为文本格式（供 LLM 读取）

    board: list[list[int]] (int 网格) 或 list[list[str]] (兼容旧字符网格)
    blocked: set of (x, y) tuples —— 封锁位，显示为 *

    输出格式（两行列号，15x15 网格）：
              11111
          012345678901234
         0 . . . . . . . . . . . . . . .
         ...
        14 . . . . . . . . . . . . . . .

    符号: .=空位  X=黑棋  O=白棋  *=封锁位(不可落子)
    """
    blocked = blocked or set()

    tens = "   "
    ones = "   "
    for i in range(N):
        t = str(i // 10)
        o = str(i % 10)
        tens += t if t != "0" else " "
        ones += o
    lines = [tens, ones]

    for y, row in enumerate(board):
        chars = []
        for x, c in enumerate(row):
            if (x, y) in blocked:
                chars.append(" *")
            elif isinstance(c, int):
                if is_black(c):
                    chars.append(" X")
                elif is_white(c):
                    chars.append(" O")
                else:
                    chars.append(" .")
            else:
                # 兼容旧 str 网格
                if c != " ":
                    chars.append(f" {c}")
                else:
                    chars.append(" .")
        line = f"{y:2d}" + "".join(chars)
        lines.append(line)
    return "\n".join(lines)


def board_to_move_sequence(board) -> str:
    """将 int 棋盘转为落子序列文本（供 Agent 理解走法时间线）

    board: list[list[int]]

    输出格式:
        黑棋(奇数): 1.(7,7) 3.(8,8) 5.(6,9) ...
        白棋(偶数): 2.(8,7) 4.(7,8) 6.(9,9) ...
    """
    entries = []
    for y in range(N):
        for x in range(N):
            v = board[y][x]
            if v:
                entries.append((v, x, y))
    entries.sort(key=lambda e: e[0])

    black_moves = []
    white_moves = []
    for seq, x, y in entries:
        if _is_black(seq):
            black_moves.append(f"{seq}.({x},{y})")
        else:
            white_moves.append(f"{seq}.({x},{y})")

    lines = ["【落子序列】"]
    if black_moves:
        lines.append("黑棋(奇数): " + " ".join(black_moves))
    if white_moves:
        lines.append("白棋(偶数): " + " ".join(white_moves))
    if not black_moves and not white_moves:
        lines.append("(空棋盘)")

    return "\n".join(lines)


def text_to_board(text):
    """将文本格式的棋盘转回二维 int 数组"""
    lines = text.strip().splitlines()
    board = [[0] * N for _ in range(N)]
    data_start = 2
    move_count = 0
    for y_idx, line in enumerate(lines):
        if y_idx < data_start:
            continue
        row_idx = y_idx - data_start
        if row_idx >= N:
            break
        content = line[2:]
        for x in range(N):
            pos = x * 2
            if pos + 1 >= len(content):
                break
            ch = content[pos + 1]
            if ch == 'X':
                move_count += 1
                # 维持奇偶性：黑=奇数
                if move_count % 2 == 0:
                    move_count += 1  # 确保奇数
                board[row_idx][x] = move_count
            elif ch == 'O':
                move_count += 1
                if move_count % 2 == 1:
                    move_count += 1  # 确保偶数
                board[row_idx][x] = move_count
    return board
