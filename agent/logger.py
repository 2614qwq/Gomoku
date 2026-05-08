"""日志系统 —— 统一日志输出到文件和控制台"""

import logging
import os
import sys
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, f"gomoku_{datetime.now().strftime('%Y%m%d')}.log")

os.makedirs(_LOG_DIR, exist_ok=True)

_FORMAT = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
    datefmt="%H:%M:%S",
)

# 文件 handler
_file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(_FORMAT)

# 控制台 handler
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_FORMAT)

# 根 logger
_root_logger = logging.getLogger("gomoku")
_root_logger.setLevel(logging.DEBUG)
_root_logger.addHandler(_file_handler)
_root_logger.addHandler(_console_handler)


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger。用法: logger = get_logger(__name__)"""
    return _root_logger.getChild(name)
