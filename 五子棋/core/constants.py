"""五子棋游戏常量定义"""

# ================== 棋盘参数 ==================
BOARD_SIZE = 15          # 棋盘大小：15×15
CELL_SIZE = 40           # 格子像素大小
MARGIN = 30              # 棋盘边距
STONE_RADIUS = 16        # 棋子半径
WINDOW_WIDTH = MARGIN * 2 + CELL_SIZE * (BOARD_SIZE - 1) + 20
WINDOW_HEIGHT = MARGIN * 2 + CELL_SIZE * (BOARD_SIZE - 1) + 40

# ================== 颜色定义 ==================
BOARD_BG = '#DCB35C'     # 棋盘背景色（棕黄色）
LINE_COLOR = '#503214'   # 网格线颜色
TEXT_COLOR = '#3C1F0A'   # 文字颜色
BLACK_STONE = 'black'    # 黑棋颜色
WHITE_STONE = 'white'    # 白棋颜色

# ================== 棋子字符 ==================
BLACK = 'X'              # 黑棋字符
WHITE = 'O'              # 白棋字符
EMPTY = ' '              # 空位字符

# ================== 星位 ==================
STAR_POINTS = [(3, 3), (11, 3), (7, 7), (3, 11), (11, 11)]

# ================== 方向向量 ==================
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]           # 四个主要方向
ADJACENT_4 = [(0, -1), (0, 1), (-1, 0), (1, 0)]          # 四邻方向
DIAGONAL_4 = [(-1, -1), (-1, 1), (1, -1), (1, 1)]        # 四斜方向
ALL_8 = ADJACENT_4 + DIAGONAL_4                            # 八方向
