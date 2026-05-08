"""控制台五子棋：双人对战，15×15棋盘，先五子连珠者胜"""

# ================== 全局变量初始化 ==================
# 初始化 15×15 的棋盘，' '表示空位，'X'表示黑棋，'O'表示白棋
board = [[' '] * 15 for _ in range(15)]
turn = 0  # 回合标识：0表示黑棋回合，1表示白棋回合

def print_board():
    """打印带行列号的棋盘
    
    功能：在控制台输出当前棋盘状态，包含行列索引便于玩家定位
    输出格式：第一行显示列号 0-14，后续每行显示行号和该行的棋子
    """
    # 打印列号表头（0-14，每个占2个字符宽度）
    print("   " + "".join(f"{i:2}" for i in range(15)))
    # 逐行打印棋盘内容
    for i, row in enumerate(board):
        # 先打印行号，再打印该行的每个棋子
        print(f"{i:2} " + " ".join(f" {c}" for c in row))

def set_chess(x, y, color):
    """在指定位置(x,y)放置棋子
    
    参数：
        x: 列坐标（0-14）
        y: 行坐标（0-14）
        color: 棋子颜色，'X'表示黑棋，'O'表示白棋
    
    返回：
        bool: 落子成功返回True，失败返回False
    """
    # 检查坐标是否在棋盘范围内（0-14）
    if not (0 <= x < 15 and 0 <= y < 15):
        print('坐标超出棋盘范围，请输入 0-14 之间的数字！')
        return False
    # 检查该位置是否已有棋子
    if board[y][x] != ' ':
        print('该位置已有棋子，请选择其他位置！')
        return False
    # 落子
    board[y][x] = color
    return True

def check_win(color):
    """检查指定颜色是否五子连珠获胜
    
    参数：
        color: 要检查的棋子颜色，'X'或'O'
    
    返回：
        bool: 获胜返回True，否则返回False
    
    检查方向：
        1. 水平方向 (1,0)
        2. 垂直方向 (0,1)
        3. 右下对角线 (1,1)
        4. 左下对角线 (1,-1)
    """
    # 遍历棋盘每个位置
    for y in range(15):
        for x in range(15):
            # 如果当前位置不是目标颜色，跳过
            if board[y][x] != color:
                continue
            # 检查四个方向（水平、垂直、右下对角线、左下对角线）
            for dx, dy in [(1,0), (0,1), (1,1), (1,-1)]:
                cnt = 1  # 连子计数器，当前位置算1个
                # 向该方向延伸检查4个棋子（总共5个）
                for s in range(1, 5):
                    nx, ny = x + dx * s, y + dy * s
                    # 如果在棋盘范围内且颜色相同，连子数加1
                    if 0 <= nx < 15 and 0 <= ny < 15 and board[ny][nx] == color:
                        cnt += 1
                    else:
                        break  # 遇到不同颜色或超出边界，停止检查该方向
                # 如果连子数达到5，获胜
                if cnt >= 5:
                    return True
    return False

def is_full():
    """检查棋盘是否已满（平局条件）
    
    返回：
        bool: 棋盘已满返回True，否则返回False
    """
    # 使用生成器表达式检查所有位置都不为空
    return all(c != ' ' for row in board for c in row)

# ================== 游戏主循环 ==================
# 游戏开始提示
print("===== 五子棋 =====")
print("黑棋(X) vs 白棋(O)，输入列和行(0-14)")

# 无限循环直到游戏结束
while True:
    # 打印当前棋盘
    print_board()
    
    # 确定当前回合的玩家
    name = '黑棋' if turn == 0 else '白棋'
    print(f'{name}回合')
    
    # 获取玩家输入
    try:
        x = int(input('列：'))  # 输入列坐标
        y = int(input('行：'))  # 输入行坐标
    except ValueError:
        # 输入不是数字的处理
        print('请输入有效数字！')
        continue
    
    # 确定当前棋子颜色
    color = 'X' if turn == 0 else 'O'
    
    # 尝试落子
    if not set_chess(x, y, color):
        continue  # 落子失败，重新输入
    
    # 检查是否获胜
    if check_win(color):
        print_board()
        print(f'{name}获胜！🎉')
        break  # 游戏结束
    
    # 检查是否平局（棋盘已满）
    if is_full():
        print_board()
        print('平局！🤝')
        break  # 游戏结束
    
    # 切换回合（0变1，1变0）
    turn = 1 - turn