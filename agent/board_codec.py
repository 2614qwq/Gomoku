"""棋盘状态编解码：在二维数组和文本格式之间互转"""

N = 15


def board_to_text(board, blocked=None):
    """将棋盘二维数组转为文本格式（供 LLM 读取）

    blocked: set of (x, y) tuples —— 封锁位，显示为 *

    输出格式（两行列号，15x15 网格）：
          11111
      012345678901234
     0 . . . . . . . . . . . . . . .
     1 . . . . . . . . . . . . . . .
     ...
    14 . . . . . . . . . . . . . . .

    符号: .=空位  X=黑棋  O=白棋  *=封锁位(不可落子)
    """
    blocked = blocked or set()

    # 两行列号头部
    tens = "   "
    ones = "   "
    for i in range(N):
        t = str(i // 10)
        o = str(i % 10)
        tens += t if t != "0" else " "
        ones += o
    lines = [tens, ones]

    # 每一行
    for y, row in enumerate(board):
        chars = []
        for x, c in enumerate(row):
            if (x, y) in blocked:
                chars.append(" *")
            elif c != " ":
                chars.append(f" {c}")
            else:
                chars.append(" .")
        line = f"{y:2d}" + "".join(chars)
        lines.append(line)
    return "\n".join(lines)


def text_to_board(text):
    """将文本格式的棋盘转回二维数组"""
    lines = text.strip().splitlines()
    board = [[" "] * N for _ in range(N)]
    data_start = 2  # 跳过两行列号头
    for y, line in enumerate(lines):
        if y < data_start:
            continue
        row_idx = y - data_start
        if row_idx >= N:
            break
        # 每两个字符为一个格子；跳过行号前缀
        content = line[2:]  # 去掉 " 0" 这样的行号
        # 每2个字符 = 1个格子: " ." / " X" / " O" / " *"
        for x in range(N):
            pos = x * 2
            if pos + 1 >= len(content):
                break
            ch = content[pos + 1]  # 取第二个字符（符号本体）
            if ch in ("X", "O"):
                board[row_idx][x] = ch
    return board
