"""CSV棋谱数据加载器

从 chess_records.csv 加载棋谱，供 RAG 检索和开局库查询使用。

棋谱格式:
  board_name, source_image, md5, grid (JSON 15×15 int 数组)
  0=空, 奇数=黑, 偶数=白
"""

import csv
import json
import os
from dataclasses import dataclass
from typing import Optional

N = 15


@dataclass
class ChessRecord:
    """单条棋谱记录"""
    board_name: str
    source_image: str
    md5: str
    grid: list[list[int]]           # 15×15 int 数组

    def get_move_sequence(self) -> list[tuple[int, int, int]]:
        """返回按序号排序的落子序列 [(x, y, 序号), ...]"""
        entries = []
        for y in range(N):
            for x in range(N):
                v = self.grid[y][x]
                if v:
                    entries.append((x, y, v))
        entries.sort(key=lambda e: e[2])
        return entries

    def count_moves(self) -> int:
        """返回总落子数"""
        return max(
            (self.grid[y][x] for y in range(N) for x in range(N) if self.grid[y][x]),
            default=0,
        )


def _parse_grid(raw: str) -> list[list[int]]:
    """将CSV中的JSON字符串解析为15×15 int网格"""
    arr = json.loads(raw)
    return [[int(v) for v in row] for row in arr]


def load_all_records(csv_path: str = None) -> list[ChessRecord]:
    """加载全部棋谱记录

    Args:
        csv_path: CSV文件路径，默认自动查找

    Returns:
        ChessRecord 列表
    """
    if csv_path is None:
        # 自动查找项目根目录下的棋谱CSV
        possible = [
            os.path.join(os.path.dirname(__file__), "..", "Chess Record", "棋谱csv数据库", "chess_records.csv"),
            os.path.join(os.path.dirname(__file__), "..", "..", "Chess Record", "棋谱csv数据库", "chess_records.csv"),
        ]
        csv_path = None
        for p in possible:
            if os.path.exists(os.path.abspath(p)):
                csv_path = os.path.abspath(p)
                break
        if csv_path is None:
            return []

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append(ChessRecord(
                    board_name=row.get("board_name", ""),
                    source_image=row.get("source_image", ""),
                    md5=row.get("md5", ""),
                    grid=_parse_grid(row["grid"]),
                ))
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
    return records


# 懒加载缓存
_records_cache: Optional[list[ChessRecord]] = None


def get_records() -> list[ChessRecord]:
    """获取棋谱记录（带缓存）"""
    global _records_cache
    if _records_cache is None:
        _records_cache = load_all_records()
    return _records_cache
