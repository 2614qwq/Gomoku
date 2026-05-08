"""Retriever 层 —— ChromaDB 查询封装

BaseRetriever 定义统一接口。子类实现具体的检索策略。
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import chromadb
from chromadb.config import Settings

from .embedder import Embedder
from .indexer import COLLECTION_NAME
from .indexer import grid_to_move_sequence, slice_sequence


@dataclass
class RetrievalResult:
    """单条检索结果"""
    doc_id: str
    document: str
    distance: float
    metadata: dict = field(default_factory=dict)


# ---- 基类 ----

class BaseRetriever(ABC):
    """检索器抽象基类"""

    def __init__(self, embedder: Optional[Embedder] = None):
        self._embedder = embedder or Embedder()
        db_dir = os.path.join(os.path.dirname(__file__), "chroma_db")
        self._client = chromadb.PersistentClient(
            path=db_dir, settings=Settings(anonymized_telemetry=False))
        self._collection = self._client.get_or_create_collection(COLLECTION_NAME)

    @abstractmethod
    def search(self, query, top_k: int = 3) -> list[RetrievalResult]:
        ...

    @abstractmethod
    def format_context(self, results: list[RetrievalResult]) -> str:
        """将检索结果转为 LLM 可读文本"""
        ...

    def _query(self, query_text: str, top_k: int = 3,
               where: Optional[dict] = None) -> list[RetrievalResult]:
        """底层 ChromaDB 查询"""
        if self._collection.count() == 0:
            return []
        query_embedding = self._embedder.embed(query_text)
        response = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        results = []
        if response["ids"] and response["ids"][0]:
            for i, doc_id in enumerate(response["ids"][0]):
                results.append(RetrievalResult(
                    doc_id=doc_id,
                    document=response["documents"][0][i] if response["documents"] else "",
                    distance=response["distances"][0][i] if response["distances"] else 1.0,
                    metadata=response["metadatas"][0][i] if response["metadatas"] else {},
                ))
        return results


# ---- 棋谱检索器 ----

class OpeningRetriever(BaseRetriever):
    """根据当前棋局落子序列检索相似棋谱开局"""

    def search(self, current_moves_text: str, top_k: int = 3) -> list[RetrievalResult]:
        """用当前落子序列文本检索

        current_moves_text: "黑1(7,7) 白2(7,8) 黑3(8,7)" 或完整序列
        """
        return self._query(
            query_text=current_moves_text,
            top_k=top_k,
            where={"doc_type": "chess_record"},
        )

    def search_by_grid(self, grid: list[list[int]], top_k: int = 3) -> list[RetrievalResult]:
        """用 15×15 二维数组检索（自动提取前N手）"""
        moves, full_seq = grid_to_move_sequence(grid)
        if not moves:
            return []

        # 根据当前手数选择最佳粒度
        total = len(moves)
        if total <= 3:
            query = slice_sequence(moves, "open3")
        elif total <= 5:
            query = slice_sequence(moves, "open5")
        elif total <= 10:
            query = slice_sequence(moves, "open10")
        else:
            query = full_seq

        return self.search(query, top_k=top_k)

    def format_context(self, results: list[RetrievalResult]) -> str:
        """格式化为 LLM 可读的棋谱参考段落（控制在 400 字以内）"""
        if not results:
            return ""

        lines = ["【棋谱参考 — 相似职业开局】"]
        for i, r in enumerate(results, 1):
            meta = r.metadata
            board = meta.get("board_name", "?")
            moves = meta.get("display_text", "") or meta.get("move_sequence", "")
            dist = r.distance
            similarity = f"{max(0, 1 - dist) * 100:.0f}%"
            # 截断过长的落子序列
            if len(moves) > 200:
                moves = moves[:200] + "..."
            lines.append(f"  {i}. [{board}] 相似度{similarity}")
            lines.append(f"     落子: {moves}")
        lines.append("  请参考以上棋谱的后续走向，但不必机械照搬。")

        context = "\n".join(lines)
        if len(context) > 500:
            context = context[:500] + "..."
        return context
