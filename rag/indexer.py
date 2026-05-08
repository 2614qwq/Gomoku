"""Indexer 层 —— 从数据源读取文档并写入 ChromaDB

基类 BaseIndexer 定义统一接口。子类各自处理不同的数据源格式。
后续添加文字资料时，只需新建 TextDocIndexer(BaseIndexer) 即可。
"""

import os
import csv
import json
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

import chromadb

from .embedder import Embedder

COLLECTION_NAME = "gomoku_knowledge"
BOARD_SIZE = 15

# ---- 棋谱文本生成工具 ----

def grid_to_move_sequence(grid: list[list[int]]) -> tuple[list[tuple[int, int, int]], str]:
    """将 15x15 网格转为排序后的落子列表和文本序列

    Returns:
        moves: [(step, x, y), ...] 按 step 升序
        text:  "黑1(7,7) 白2(7,8) 黑3(6,7) ..."
    """
    moves = []
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            v = grid[y][x]
            if v > 0:
                moves.append((v, x, y))
    moves.sort(key=lambda m: m[0])

    parts = []
    for step, x, y in moves:
        color = "黑" if step % 2 == 1 else "白"
        parts.append(f"{color}{step}({x},{y})")
    return moves, " ".join(parts)


def slice_sequence(moves: list[tuple[int, int, int]], granularity: str) -> str:
    """从落子列表中切分指定粒度的文本

    granularity: "open3" / "open5" / "open10" / "full"
    """
    limits = {"open3": 3, "open5": 5, "open10": 10, "full": len(moves)}
    limit = limits.get(granularity, len(moves))
    sliced = moves[:limit]
    parts = []
    for step, x, y in sliced:
        color = "黑" if step % 2 == 1 else "白"
        parts.append(f"{color}{step}({x},{y})")
    return " ".join(parts)


# ---- 基类 ----

class BaseIndexer(ABC):
    """索引器抽象基类"""

    def __init__(self, embedder: Embedder):
        self._embedder = embedder

    @abstractmethod
    def index(self, collection) -> int:
        """执行索引，返回新增文档数"""
        ...


# ---- 棋谱索引器 ----

class ChessRecordIndexer(BaseIndexer):
    """从 CSV 读取棋谱二维数组，多粒度切分后写入 ChromaDB"""

    GRANULARITIES = ["open3", "open5", "open10", "full"]

    def __init__(self, csv_path: str, embedder: Embedder):
        super().__init__(embedder)
        self._csv_path = csv_path

    def index(self, collection) -> int:
        """读取 CSV → 生成文档 → 批量 embed → 写入 ChromaDB"""
        if not os.path.exists(self._csv_path):
            raise FileNotFoundError(f"CSV 不存在: {self._csv_path}")

        # 1. 读取并解析 CSV
        records = self._load_csv()
        if not records:
            print("[Indexer] CSV 为空，跳过")
            return 0

        # 2. 生成所有文档（先不 embed），过滤重复
        docs = []
        ids = []
        metadatas = []
        seen_ids = set()
        skipped = 0

        for rec in records:
            for gran in self.GRANULARITIES:
                doc_id = f"chess:{rec['md5']}:{gran}"

                # 去重：本地已见过 或 ChromaDB 已存在
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)

                existing = collection.get(ids=[doc_id])
                if existing and existing["ids"]:
                    skipped += 1
                    continue

                moves, full_seq = grid_to_move_sequence(rec["grid"])
                doc_text = slice_sequence(moves, gran)
                if not doc_text.strip():
                    continue

                docs.append(doc_text)
                ids.append(doc_id)
                metadatas.append({
                    "doc_type": "chess_record",
                    "source": rec["source_image"],
                    "board_name": rec["board_name"],
                    "md5": rec["md5"],
                    "granularity": gran,
                    "total_moves": len(moves),
                    "display_text": full_seq,
                })

        if not docs:
            print(f"[Indexer] 全部已入库，跳过 {skipped} 条")
            return 0

        print(f"[Indexer] 待入库 {len(docs)} 条（跳过 {skipped} 条重复）")

        # 3. 批量 embed + 分批写入（ChromaDB 单次 add 上限约 500 条）
        total = 0
        add_batch = 100
        for i in range(0, len(docs), add_batch):
            chunk_docs = docs[i:i + add_batch]
            chunk_ids = ids[i:i + add_batch]
            chunk_meta = metadatas[i:i + add_batch]

            print(f"[Indexer] embedding {i + 1}-{i + len(chunk_docs)}/{len(docs)} ...")
            embeddings = self._embedder.embed_batch(chunk_docs)

            collection.add(ids=chunk_ids, documents=chunk_docs,
                           embeddings=embeddings, metadatas=chunk_meta)
            total += len(chunk_docs)

        print(f"[Indexer] 入库完成: {total} 条")
        return total

    def _load_csv(self) -> list[dict]:
        rows = []
        with open(self._csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row["grid"] = json.loads(row.get("grid", "[]"))
                except json.JSONDecodeError:
                    continue
                if not row.get("md5"):
                    row["md5"] = hashlib.md5(
                        json.dumps(row["grid"]).encode()
                    ).hexdigest()
                rows.append(row)
        return rows
