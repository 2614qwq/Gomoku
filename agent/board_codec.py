"""棋盘状态编解码：在二维数组和文本格式之间互转"""

N = 15


def board_to_text(board):
    """将棋盘二维数组转为文本格式（供 LLM 读取）

    输出示例：
      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4
    0 . . . . . . . . . . . . . . .
    1 . . . . . . . . . . . . . . .
    """
    header = "   " + "".join(f"{i:2}" for i in range(N))
    lines = [header]
    for y, row in enumerate(board):
        line = f"{y:2} " + " ".join(f" {c}" if c != " " else " ." for c in row)
        lines.append(line)
    return "\n".join(lines)


def text_to_board(text):
    """将文本格式的棋盘转回二维数组"""
    lines = text.strip().splitlines()
    board = [[" "] * N for _ in range(N)]
    for y, line in enumerate(lines):
        if y == 0:
            continue  # 跳过表头
        tokens = line.split()
        if not tokens:
            continue
        row = tokens[1:]  # 去掉行号
        for x, token in enumerate(row):
            if x >= N:
                break
            ch = token.strip()
            if ch in ("X", "O"):
                board[y][x] = ch
    return board
