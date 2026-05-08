"""PromptLoader —— 加载 prompts/*.txt"""

import os


class PromptLoader:
    """启动时一次性加载所有角色提示词到内存"""

    def __init__(self, prompt_dir: str = None):
        if prompt_dir is None:
            prompt_dir = os.path.dirname(os.path.abspath(__file__))
        self._cache: dict[str, str] = {}
        for filename in os.listdir(prompt_dir):
            if filename.endswith(".txt"):
                role = filename[:-4]  # "tactical", "defense", ...
                path = os.path.join(prompt_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    self._cache[role] = f.read()

    def get(self, role: str) -> str:
        return self._cache.get(role, "")
