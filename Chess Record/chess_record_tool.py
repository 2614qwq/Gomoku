"""棋谱处理工具 —— 批量扫描棋谱图片，并行调用视觉大模型生成 15×15 二维数组存入 CSV

用法:
  python chess_record_tool.py                     # 批量处理（默认3线程）
  python chess_record_tool.py --workers 5         # 5线程并行
  python chess_record_tool.py <图片路径>           # 处理单张图片
"""

import os
import sys
import re
import json
import base64
import hashlib
import argparse
import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

# ============================================================================
# 配置
# ============================================================================

IMAGE_DIR = "棋谱"
CSV_DIR = "棋谱csv数据库"
CSV_FILE = "chess_records.csv"
BOARD_SIZE = 15
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

SYSTEM_PROMPT = """你是一个五子棋职业棋谱识别专家。

【重要规则说明】
五子棋职业比赛(连珠规则)中，对局不一定要下出5颗连成一线才结束。
只要一方走出四三杀、双活三杀、多路连续追胜等必胜定式，
对手无论如何防守都挡不住，棋局直接判定该方获胜并提前结束。
因此职业棋谱经常只记录到第15-20手就终止，棋盘上看不到五连，
这是正常的，不是棋谱不完整。

【识别任务】
请分析这张棋谱图片，棋盘为15x15标准棋盘。
图中数字代表落子顺序(1=黑棋第1手,2=白棋第1手,3=黑棋第2手,依此类推)。

请将整个棋局输出为一个15x15的二维数组:
- 无数字标记的格子填 0
- 有数字标记的格子填对应数字(正整数)

输出格式(严格JSON，不要代码块标记```，直接输出数组):
[[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
 [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
 ...
 [0,0,0,0,0,0,0,1,2,3,0,0,0,0,0],
 ...]

规则:
- 第1行=棋盘最上行(y=0), 第15行=棋盘最下行(y=14)
- 每行内第1个元素=最左列(x=0), 第15个=最右列(x=14)
- 数字从小到大排列(1,2,3...), 奇数=黑棋 偶数=白棋
- 如果棋盘上没有显示五连，但数字序列提前终止，按连珠规则理解：该局面已是某一方必胜定式"""

# CSV 字段（含 md5 去重）
CSV_FIELDS = ["board_name", "source_image", "md5", "grid"]


# ============================================================================
# MD5 工具
# ============================================================================

def file_md5(path: str) -> str:
    """计算文件 MD5"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================================
# CSV 操作（含 MD5 去重）
# ============================================================================

class CsvStore:
    """棋谱 CSV 数据库，支持 MD5 去重（线程安全）"""

    def __init__(self):
        os.makedirs(CSV_DIR, exist_ok=True)
        self._filepath = os.path.join(CSV_DIR, CSV_FILE)
        self._records: list[dict] = []
        self._md5_set: set[str] = set()
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        """加载现有 CSV"""
        if not os.path.exists(self._filepath):
            return
        with open(self._filepath, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._records.append(row)
                if row.get("md5"):
                    self._md5_set.add(row["md5"])

    def exists(self, md5: str) -> bool:
        with self._lock:
            return md5 in self._md5_set

    def get_count(self) -> int:
        with self._lock:
            return len(self._records)

    def add(self, board_name: str, source_image: str, md5: str, grid: list[list[int]]):
        """添加一条棋谱记录并持久化（线程安全）"""
        grid_json = json.dumps(grid, ensure_ascii=False)
        with self._lock:
            self._records = [r for r in self._records if r.get("board_name") != board_name]
            self._records.append({
                "board_name": board_name,
                "source_image": source_image,
                "md5": md5,
                "grid": grid_json,
            })
            self._md5_set.add(md5)
            self._save()

    def _save(self):
        with open(self._filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in self._records:
                writer.writerow(row)


# ============================================================================
# 视觉模型客户端
# ============================================================================

class VisionChessClient:
    """调用 qwen3-vl-plus 分析棋谱图片"""

    def __init__(self):
        self._client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def analyze(self, image_path: str) -> list[list[int]]:
        """分析棋谱图片，返回 15×15 二维数组"""
        image_data_url = self._encode_image(image_path)

        response = self._client.chat.completions.create(
            model="qwen3.5-omni-plus-2026-03-15",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                        {"type": "text", "text": "请识别这张棋谱图片，输出15x15二维数组JSON。"},
                    ],
                },
            ],
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        return self._parse_grid(raw)

    def _encode_image(self, path: str) -> str:
        ext = Path(path).suffix.lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg",
                "jpeg": "image/jpeg", "webp": "image/webp",
                "bmp": "image/bmp"}.get(ext, "image/png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"

    def _parse_grid(self, raw: str) -> list[list[int]]:
        print(f"  [Vision] 返回(前200字符): {raw[:200]}")

        # 按优先级尝试多种解析策略
        for strategy in [
            self._extract_json_fence,       # ```json ... ```
            self._extract_bare_array,       # [[...],...]
            self._extract_coordinates,      # 兜底：从坐标列表重建网格
        ]:
            grid = strategy(raw)
            if grid:
                return grid

        raise ValueError(f"无法解析二维数组。原始输出:\n{raw[:500]}")

    def _extract_json_fence(self, raw: str) -> list[list[int]] | None:
        """提取 ```json ... ``` 代码块中的数组"""
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if m:
            return self._try_parse_json(m.group(1).strip())
        return None

    def _extract_bare_array(self, raw: str) -> list[list[int]] | None:
        """提取裸 [[...],...] 数组"""
        m = re.search(r"\[\s*\[[\d,\s\[\]]+]]", raw, re.DOTALL)
        if m:
            return self._try_parse_json(m.group())
        return None

    def _extract_coordinates(self, raw: str) -> list[list[int]] | None:
        """兜底：从 '(x,y): N' 或 'step N: (x,y)' 等坐标文本重建 15x15 网格"""
        patterns = [
            r'\((\d{1,2}),\s*(\d{1,2})\)\s*[:：]\s*(\d{1,3})',   # (x,y): N
            r'[sS]tep\s*(\d{1,3})\s*[:：]\s*\((\d{1,2}),\s*(\d{1,2})\)',  # step N: (x,y)
            r'(\d{1,3})\s*[:：]\s*\((\d{1,2}),\s*(\d{1,2})\)',    # N: (x,y)
            r'(\d{1,3})\s*[:,]\s*(\d{1,2})\s*[,，]\s*(\d{1,2})',  # N: x, y
        ]
        for pat in patterns:
            matches = re.findall(pat, raw)
            if len(matches) >= 3:  # 至少3手棋才可信
                grid = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
                for m in matches:
                    try:
                        nums = [int(n) for n in m]
                        if pat.startswith(r'\((\d'):
                            x, y, step = nums[0], nums[1], nums[2]
                        elif 'step' in pat.lower():
                            step, x, y = nums[0], nums[1], nums[2]
                        elif pat.startswith(r'(\d{1,3})\s*[:：]'):
                            step, x, y = nums[0], nums[1], nums[2]
                        else:
                            step, x, y = nums[0], nums[1], nums[2]
                        if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
                            grid[y][x] = step
                    except (ValueError, IndexError):
                        continue
                if any(any(v > 0 for v in row) for row in grid):
                    return grid
            return None
        return None

    def _try_parse_json(self, text: str) -> list[list[int]] | None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            cleaned = re.sub(r'[^\d\[\],\s-]', '', text)
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                return None

        if not isinstance(data, list) or len(data) != BOARD_SIZE:
            return None
        grid = []
        for row in data:
            if not isinstance(row, list) or len(row) != BOARD_SIZE:
                return None
            grid.append([int(v) if isinstance(v, (int, float)) else 0 for v in row])
        return grid


# ============================================================================
# 棋盘打印
# ============================================================================

def print_grid(grid: list[list[int]]):
    print(f"\n{'─' * 45}")
    for y, row in enumerate(grid):
        cells = []
        for v in row:
            if v == 0:
                cells.append(" ·")
            elif v % 2 == 1:
                cells.append(f"●{v:1d}")
            else:
                cells.append(f"○{v:1d}")
        print("".join(cells))
    print(f"{'─' * 45}")
    print(f"  ●=黑  ○=白  数字=落子序号\n")


# ============================================================================
# 单张处理
# ============================================================================

def process_one(image_path: str, board_name: str, store: CsvStore) -> dict:
    """处理单张棋谱图片。返回 {"status": "ok"|"skip"|"fail", "name": ..., "info": ...}"""

    md5 = file_md5(image_path)
    source = os.path.basename(image_path)

    if store.exists(md5):
        return {"status": "skip", "name": source, "info": f"MD5重复 {md5[:12]}..."}

    # 每个线程独立创建 client（OpenAI client 线程安全，但各自实例更干净）
    client = VisionChessClient()

    try:
        grid = client.analyze(image_path)
    except Exception as e:
        return {"status": "fail", "name": source, "info": str(e)[:80]}

    if len(grid) != BOARD_SIZE or any(len(r) != BOARD_SIZE for r in grid):
        return {"status": "fail", "name": source, "info": "维度不符"}

    non_zero = sum(1 for r in grid for v in r if v > 0)
    store.add(board_name, source, md5, grid)
    return {"status": "ok", "name": source, "info": f"{non_zero}手", "grid": grid}


# ============================================================================
# 主程序
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="棋谱图片 → 15×15 二维数组 → CSV（并行+MD5去重）")
    parser.add_argument("image", nargs="?", default=None,
                        help="单张图片路径。不指定则批量处理 棋谱/ 文件夹")
    parser.add_argument("--name", "-n", default=None,
                        help="棋谱名称。批量模式默认取文件名")
    parser.add_argument("--workers", "-w", type=int, default=3,
                        help="并行线程数（默认3）")
    args = parser.parse_args()

    store = CsvStore()

    # ---- 单张模式 ----
    if args.image:
        if not os.path.exists(args.image):
            print(f"错误: 图片不存在 —— {args.image}")
            sys.exit(1)
        board_name = args.name or Path(args.image).stem
        print(f"=== 单张模式: {board_name} ===\n")
        result = process_one(args.image, board_name, store)
        if result["status"] == "ok":
            print_grid(result.get("grid", []))
        print(f"结果: {result['status']} — {result['info']}")
        return

    # ---- 批量模式 ----
    if not os.path.isdir(IMAGE_DIR):
        print(f"错误: 棋谱目录不存在 —— {IMAGE_DIR}")
        sys.exit(1)

    images = sorted(
        p for p in Path(IMAGE_DIR).iterdir()
        if p.suffix.lower() in SUPPORTED_EXT
    )
    if not images:
        print(f"棋谱目录为空（支持格式: {', '.join(SUPPORTED_EXT)}）")
        sys.exit(0)

    # 预处理：计算 MD5 并过滤已入库的
    tasks = []
    skip_first = 0
    for img_path in images:
        img_str = str(img_path)
        md5 = file_md5(img_str)
        if store.exists(md5):
            skip_first += 1
            continue
        board_name = args.name or img_path.stem
        tasks.append((img_str, board_name))

    before_count = store.get_count()
    total_images = len(images)
    new_images = len(tasks)
    workers = min(args.workers, new_images) if new_images else 1

    print(f"=== 批量模式 | {workers} 线程并行 ===")
    print(f"扫描: {total_images} 张 | 已入库: {skip_first} | 待处理: {new_images}")
    if not tasks:
        print("全部已入库，无需处理。")
        return
    print()

    # 并行处理
    ok_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_one, path, name, store): path
            for path, name in tasks
        }
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            status = result["status"]
            if status == "ok":
                ok_count += 1
                grid_info = f"[{result['info']}]"
            elif status == "skip":
                pass  # 不应出现（已预过滤），但容错
            else:
                fail_count += 1
                grid_info = f"[失败: {result['info']}]"
            print(f"  [{i}/{new_images}] {result['name']:20s} {result['status']:4s} {grid_info}")

    total = store.get_count()
    print(f"\n=== 完成 ===")
    print(f"入库 {ok_count} | 跳过 {skip_first} | 失败 {fail_count}")
    print(f"CSV 总数: {total} | 本次新增: {ok_count}")


if __name__ == "__main__":
    main()
