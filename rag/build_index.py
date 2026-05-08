"""RAG 索引构建 CLI

用法:
    python -m rag.build_index              # 增量构建
    python -m rag.build_index --force      # 清空重建
"""

import os
import sys
import argparse
import time

import chromadb
from chromadb.config import Settings

from .embedder import Embedder
from .indexer import ChessRecordIndexer, COLLECTION_NAME

# CSV 路径（相对于项目根目录）
CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "Chess Record", "棋谱csv数据库", "chess_records.csv"
)


def main():
    parser = argparse.ArgumentParser(description="RAG 向量索引构建")
    parser.add_argument("--force", action="store_true", help="清空 collection 后重建")
    parser.add_argument("--csv", default=None, help=f"CSV 路径（默认: {CSV_PATH}）")
    args = parser.parse_args()

    csv_path = args.csv or os.path.abspath(CSV_PATH)
    if not os.path.exists(csv_path):
        print(f"错误: CSV 不存在 —— {csv_path}")
        sys.exit(1)

    t0 = time.time()

    # 连接 ChromaDB（持久化存储到 rag/chroma_db/）
    db_dir = os.path.join(os.path.dirname(__file__), "chroma_db")
    client = chromadb.PersistentClient(path=db_dir, settings=Settings(anonymized_telemetry=False))

    # 获取或创建 collection
    if args.force:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"[ChromaDB] 已删除旧 collection: {COLLECTION_NAME}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "五子棋知识库：棋谱 + 文字资料"},
    )

    print(f"[ChromaDB] Collection: {COLLECTION_NAME} ({collection.count()} 条)")

    # 索引棋谱
    embedder = Embedder()
    indexer = ChessRecordIndexer(csv_path, embedder)
    new_count = indexer.index(collection)

    elapsed = time.time() - t0
    print(f"\n=== 完成 === 新增 {new_count} 条 | 总数 {collection.count()} 条 | 耗时 {elapsed:.1f}s")


if __name__ == "__main__":
    main()
