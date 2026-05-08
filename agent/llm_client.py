"""阿里云百炼 LLM 客户端 —— 封装 DashScope API 调用"""

import os
import re
from openai import OpenAI


class LLMClient:
    """LLM 调用客户端，严格沿用原有 API 方式"""

    def __init__(self, model: str = "qwen-plus", temperature: float = 0.1):
        self._client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self._model = model
        self._temperature = temperature

    def chat(self, system_prompt: str, user_message: str,
             response_format: str = "text") -> str:
        """单次 LLM 调用"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def parse_move(self, text: str):
        """从 LLM 输出中提取落子坐标。优先 MOVE:x,y，兜底取最后两个数字"""
        m = re.search(r"MOVE\s*:\s*(\d+)\s*[,\s]\s*(\d+)", text, re.IGNORECASE)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            if 0 <= x < 15 and 0 <= y < 15:
                return (x, y)
        nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", text) if 0 <= int(n) < 15]
        if len(nums) >= 2:
            return (nums[-2], nums[-1])
        return None
