"""阿里云百炼 LLM 客户端 —— 封装 DashScope API 调用"""

import json
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
             response_format: str = "text", max_tokens: int = 256) -> str:
        """单次 LLM 调用"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def chat_with_tools(self, system_prompt: str, user_message: str,
                         tools: list[dict], max_tokens: int = 512) -> dict:
        """支持 tool-calling 的 LLM 调用

        Returns:
            {"content": str | None, "tool_calls": list | None}
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=self._temperature,
            max_tokens=max_tokens,
        )
        msg = response.choices[0].message
        result = {"content": msg.content, "tool_calls": None}
        if msg.tool_calls:
            result["tool_calls"] = []
            for tc in msg.tool_calls:
                raw_args = tc.function.arguments
                if isinstance(raw_args, str):
                    try:
                        raw_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        pass
                result["tool_calls"].append({
                    "name": tc.function.name,
                    "arguments": raw_args,
                })
        return result

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
