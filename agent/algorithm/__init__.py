"""五子棋算法模块 —— 规则驱动的棋型检测、评估与搜索

提供与 LLM 多智能体系统互补的传统算法能力：
  - pattern: 棋型检测（活四/冲四/活三/冲三/活二）
  - evaluate: 局面评估函数
  - search: Minimax + Alpha-Beta 剪枝搜索
"""

from .pattern import (
    extract_patterns,
    find_immediate_win,
    find_must_block,
    find_double_threat_moves,
    find_existing_live3_blocks,
    scan_threats,
)
from .evaluate import (
    evaluate_board,
    score_position,
    WEIGHTS,
)
from .search import get_best_move
