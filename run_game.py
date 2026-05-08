"""五子棋（万宁招式版）启动脚本

直接运行即可启动游戏:
    python run_game.py
"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from 五子棋.ui.game_window import GomokuGUI

if __name__ == '__main__':
    app = GomokuGUI()
    app.run()
