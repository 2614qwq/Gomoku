"""tkinter五子棋：双人对战，无额外依赖"""

# ================== 导入必要模块 ==================
import tkinter as tk  # 导入 tkinter GUI 库
from tkinter import messagebox  # 导入消息框用于显示游戏结果
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from agent import GomokuAgent  # 导入五子棋智能体

# ================== 全局常量定义 ==================
N = 15           # 棋盘大小：15×15
S = 40           # 格子像素大小：每个格子40像素
M = 30           # 棋盘边距：棋盘边缘到窗口边缘的距离
R = 16           # 棋子半径：16像素
W = M*2 + S*(N-1)  # 窗口尺寸：两边边距 + (15-1)个格子的总宽度

# ================== 游戏状态变量 ==================
# 初始化 15×15 的棋盘，' '表示空位，'X'表示黑棋，'O'表示白棋
board = [[' ']*N for _ in range(N)]
turn = 0  # 回合标识：0表示黑棋回合，1表示白棋回合
game_mode = 0     # 0=双人, 1=人机(玩家黑), 2=人机(玩家白)
agent = None      # GomokuAgent 实例

# ================== GUI 初始化 ==================
root = tk.Tk()  # 创建主窗口
root.title("五子棋")  # 设置窗口标题
# 创建画布：背景色为棕黄色(#DCB35C)，宽高为窗口尺寸+额外留白
cv = tk.Canvas(root, width=W+20, height=W+40, bg='#DCB35C')
cv.pack()  # 将画布添加到窗口

def draw_board():
    """绘制棋盘、棋子和状态信息
    
    绘制内容：
        1. 棋盘网格线
        2. 五个星位（围棋中的天元和四星）
        3. 所有棋子
        4. 当前回合提示文字
    """
    cv.delete('all')  # 清空画布，准备重绘
    
    # ================== 绘制网格线 ==================
    for i in range(N):
        # 绘制横线：从左到右
        cv.create_line(M, M+i*S, M+(N-1)*S, M+i*S, fill='#503214', width=2)
        # 绘制竖线：从上到下
        cv.create_line(M+i*S, M, M+i*S, M+(N-1)*S, fill='#503214', width=2)
    
    # ================== 绘制星位 ==================
    # 五个标准星位位置：(3,3)、(11,3)、(7,7)天元、(3,11)、(11,11)
    for p in [(3,3),(11,3),(7,7),(3,11),(11,11)]:
        # 绘制小圆点作为星位
        cv.create_oval(M+p[0]*S-4, M+p[1]*S-4, M+p[0]*S+4, M+p[1]*S+4, fill='#503214')
    
    # ================== 绘制棋子 ==================
    for r in range(N):  # 遍历每一行
        for c in range(N):  # 遍历每一列
            clr = board[r][c]  # 获取当前位置的棋子
            if clr == ' ':  # 空位跳过
                continue
            # 计算棋子中心坐标
            x, y = M+c*S, M+r*S
            # 确定棋子填充色：黑棋为黑色，白棋为白色
            fill_c = 'black' if clr == 'X' else 'white'
            # 绘制圆形棋子，带灰色边框
            cv.create_oval(x-R, y-R, x+R, y+R, fill=fill_c, outline='gray')
    
    # ================== 绘制状态文字 ==================
    # 如果游戏还未结束（无人获胜且棋盘未满），显示当前回合
    if not check_win(board, 'X') and not check_win(board, 'O') and not is_full(board):
        name = "黑棋" if turn == 0 else "白棋"
        # 在画布底部中央显示当前回合提示
        cv.create_text(W//2+10, W+20, text=f"当前回合：{name}", font=('SimHei',14), fill='#3C1F0A')

def click(ev):
    """处理鼠标点击事件，实现落子逻辑
    
    参数：
        ev: 鼠标点击事件对象，包含点击坐标 ev.x 和 ev.y
    """
    global turn, board  # 声明使用全局变量
    
    # ================== 计算落子位置 ==================
    # 将鼠标坐标转换为棋盘行列：四舍五入到最近的交叉点
    c = round((ev.x - M) / S)  # 列索引
    r = round((ev.y - M) / S)  # 行索引
    
    # ================== 落子验证 ==================
    # 检查位置是否合法且为空
    if not (0 <= c < N and 0 <= r < N) or board[r][c] != ' ':
        return  # 不合法，直接返回
    
    # 检查游戏是否已经结束（获胜或平局）
    if check_win(board, 'X') or check_win(board, 'O') or is_full(board):
        return  # 游戏已结束，不处理
    
    # ================== 执行落子 ==================
    # 根据当前回合确定棋子颜色并落子
    board[r][c] = 'X' if turn == 0 else 'O'
    draw_board()  # 重绘棋盘
    
    # ================== 游戏状态判断 ==================
    color = board[r][c]  # 获取刚落下的棋子颜色
    
    # 检查是否获胜
    if check_win(board, color):
        name = "黑棋" if color == 'X' else "白棋"
        messagebox.showinfo("游戏结束", f"{name}获胜！🎉")
        # 重置游戏
        board = [[' ']*N for _ in range(N)]
        turn = 0
        draw_board()
        if game_mode == 2:
            root.after(500, ai_move)
    # 检查是否平局（棋盘已满）
    elif is_full(board):
        messagebox.showinfo("游戏结束", "平局！🤝")
        # 重置游戏
        board = [[' ']*N for _ in range(N)]
        turn = 0
        draw_board()
        if game_mode == 2:
            root.after(500, ai_move)
    else:
        # 游戏继续，切换回合
        turn = 1 - turn
        if game_mode != 0:
            root.after(300, ai_move)

def check_win(board, color):
    """检查指定颜色是否五子连珠获胜
    
    参数：
        board: 当前棋盘状态
        color: 要检查的棋子颜色，'X'或'O'
    
    返回：
        bool: 获胜返回True，否则返回False
    
    检查方向：
        1. 水平方向 (1,0)
        2. 垂直方向 (0,1)
        3. 右下对角线 (1,1)
        4. 左下对角线 (1,-1)
    """
    for r in range(N):  # 遍历每一行
        for c in range(N):  # 遍历每一列
            if board[r][c] != color:
                continue  # 当前位置不是目标颜色，跳过
            # 检查四个方向
            for dx, dy in [(1,0),(0,1),(1,1),(1,-1)]:
                cnt = 1  # 连子计数器
                # 向该方向延伸检查4个棋子
                for s in range(1,5):
                    nx, ny = c + dx*s, r + dy*s
                    if 0 <= nx < N and 0 <= ny < N and board[ny][nx] == color:
                        cnt += 1
                    else:
                        break  # 遇到不同颜色或边界，停止检查
                if cnt >= 5:
                    return True  # 五子连珠，获胜
    return False

def is_full(board):
    """检查棋盘是否已满（平局条件）
    
    参数：
        board: 当前棋盘状态
    
    返回：
        bool: 棋盘已满返回True，否则返回False
    """
    # 检查所有位置都不为空
    return all(c != ' ' for row in board for c in row)

# ================== 游戏模式选择 ==================
def show_mode_selection():
    """显示游戏模式选择对话框"""
    dlg = tk.Toplevel(root)
    dlg.title("选择游戏模式")
    dlg.geometry("300x200")
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()

    tk.Label(dlg, text="请选择游戏模式", font=('SimHei', 14)).pack(pady=20)

    def set_mode(m):
        global game_mode, agent
        game_mode = m
        if m != 0:
            agent = GomokuAgent()
        dlg.destroy()
        draw_board()
        if m == 2:  # 玩家执白，AI先手
            root.after(500, ai_move)

    btn_font = ('SimHei', 11)
    tk.Button(dlg, text="双人对战", width=20, font=btn_font,
              command=lambda: set_mode(0)).pack(pady=4)
    tk.Button(dlg, text="人机对战（执黑）", width=20, font=btn_font,
              command=lambda: set_mode(1)).pack(pady=4)
    tk.Button(dlg, text="人机对战（执白）", width=20, font=btn_font,
              command=lambda: set_mode(2)).pack(pady=4)


# ================== AI 落子 ==================
def ai_move():
    """AI 执行落子"""
    global turn, board
    result = agent.get_move(board, turn)
    if result is None:
        return
    x, y = result
    board[y][x] = 'X' if turn == 0 else 'O'
    draw_board()
    color = board[y][x]
    if check_win(board, color):
        name = "黑棋" if color == 'X' else "白棋"
        messagebox.showinfo("游戏结束", f"{name}获胜！🎉")
        board = [[' ']*N for _ in range(N)]
        turn = 0
        draw_board()
        if game_mode == 2:
            root.after(500, ai_move)
    elif is_full(board):
        messagebox.showinfo("游戏结束", "平局！🤝")
        board = [[' ']*N for _ in range(N)]
        turn = 0
        draw_board()
        if game_mode == 2:
            root.after(500, ai_move)
    else:
        turn = 1 - turn


# ================== 事件绑定与启动 ==================
# 绑定鼠标左键点击事件到 click 函数
cv.bind('<Button-1>', click)
# 显示模式选择对话框（选择后自动绘制棋盘）
show_mode_selection()
# 进入 GUI 主循环，开始监听事件
root.mainloop()
