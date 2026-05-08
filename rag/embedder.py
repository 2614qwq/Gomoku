"""Embedding API 封装 —— 调用 text-embedding-v4"""

import os
import time
from openai import OpenAI


class Embedder:
    """DashScope text-embedding-v4 封装，内置速率控制"""

    def __init__(self, model: str = "text-embedding-v4", rate_limit: float = 0.2):
        self._client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self._model = model
        self._rate_limit = rate_limit

    def embed(self, text: str) -> list[float]:
        """对单条文本生成 embedding"""
        results = self.embed_batch([text])
        return results[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding，自动分批 + 限速"""
        all_embeddings = []
        batch_size = 10  # text-embedding-v4 单次最大 10 条

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self._client.embeddings.create(
                model=self._model,
                input=batch,
                encoding_format="float",
            )
            # 按索引排序后提取向量
            sorted_data = sorted(response.data, key=lambda d: d.index)
            all_embeddings.extend([d.embedding for d in sorted_data])
            time.sleep(self._rate_limit)

        return all_embeddings

    @property
    def model_name(self) -> str:
        return self._model
