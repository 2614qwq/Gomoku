# AI vs AI 性能问题分析

## 当前 AI 调用链路

```
trigger_ai_move()
  └─ orchestrator.analyze(controller)
       ├─ phase_check        (本地, <1ms)
       ├─ tactical           (LLM: qwen-turbo, ~2-3s)
       ├─ defense            (LLM: qwen-turbo, ~2-3s)   ← 等 tactical 完成后才执行
       ├─ devil_advocate     (LLM: qwen-plus, ~2-3s)    ← 仅 complex 阶段
       └─ chief              (LLM: qwen-plus, ~2-3s)
```

**每步 AI 落子耗时：6-12 秒**（3-4 次串行 LLM 调用）。

一局 AI vs AI 最多 225 步，理论上可能需要 **30 分钟以上**。

---

## 瓶颈 1：LLM 调用完全串行，tactical 与 defense 无依赖却排队执行

**现状：** LangGraph 图定义为 `tactical → defense → chief`，三节点严格顺序执行。但 tactical（进攻分析）和 defense（防守分析）读取的是同一份 `game_report`，彼此之间没有数据依赖。

**影响：** 每步浪费 2-3 秒。

**修复方案：**

- **方案 A（推荐）：** 将 tactical 和 defense 改为并行节点。LangGraph 支持 `builder.add_edge(START, "tactical")` + `builder.add_edge(START, "defense")`，二者同时从 START 出发，在 chief 节点汇聚。预期每步缩短 2-3 秒。

- **方案 B：** 使用 `asyncio.gather()` 在单个节点内并发调用两个 Agent 的 LLM。

- **注意：** 需要确保 `LLMClient` 的 `OpenAI` 客户端实例是线程安全的。当前每个 Agent 持有自己的 `LLMClient` 实例（qwen-turbo），互不干扰，可以安全并行。

---

## 瓶颈 2：简单局面仍然调用 3 个 LLM Agent

**现状：** `classify_phase()` 返回 `simple` 时，仍然走 `tactical → defense → chief` 三次 LLM 调用。只有 `emergency`（对方四连）才跳过 LLM。

**影响：** 开局和简单中盘（无直接威胁）仍然耗费 6 秒/步。

**修复方案：**

- **方案 A：** `simple` 阶段只调用 1 个 LLM Agent（如只调用 chief，或只调用 tactical），跳过 defense 和 devil。

- **方案 B：** `simple` 阶段直接使用引擎（`engine.get_best_move`），完全跳过 LLM。引擎对简单局面的判断已经足够准确。

- **方案 C：** 引擎先计算最佳落子，若评分显著高于第二名（如差距 > 10 倍），直接采纳，不调用 LLM（"明显手"快速通道）。

---

## 瓶颈 3：AI vs AI 的 root.after(800) 人为延迟

**现状：** `game_window.py:155` 中 `self._root.after(800, self._trigger_ai_move)` 在每步 AI 落子后额外等待 800ms。

**影响：** 一局 200+ 步，仅此延迟就累计 160 秒（近 3 分钟纯等待）。

**修复方案：**

- 将 800ms 缩短为 100-200ms（足够 UI 刷新即可）。
- 或使用 `root.update_idletasks()` 强制刷新后再立即调用，不需要固定延迟。

---

## 瓶颈 4：tactical 和 defense 共识时仍走完整流程

**现状：** 当 tactical 和 defense 推荐同一落子位置且 confidence 都 > 0.8 时，仍要经过 chief（又要一次 LLM 调用）才能输出。

**影响：** 多余 1 次 LLM 调用。

**修复方案：**

- **方案 A：** 在 orchestrator 的 `_chief_node` 之前加入短路逻辑：若 tactical 和 defense 的 `move` 相同且 `confidence > 0.8`，直接采纳，跳过 chief 的 LLM 调用。

- **方案 B：** 更激进——tactical 和 defense 任一 confidence > 0.95（几乎必胜步），直接返回，不等对方也不等 chief。

---

## 瓶颈 5：每步都实时计算 225 个候选格评分

**现状：** `GameInfoExtractor._candidates_section()` 每步对 225 个格子调用 `_quick_score()`（遍历 4 方向各最多 5 步），即使很多格子周围完全为空。

**影响：** 每步约 0.1-0.3 秒 CPU 时间。虽小但累积可观。

**修复方案：**

- **方案 A：** 只评估已有棋子周围 2 格范围内的空位（通常从 225 降至 30-60 个候选）。

- **方案 B：** 直接复用 `engine.get_best_move` 的 `candidates` 列表（engine 已经在做同样的事），避免重复计算。

- **方案 C：** 缓存评分结果，仅增量更新受上一步落子影响的格子。

---

## 瓶颈 6：历史记忆使 Prompt 越来越长

**现状：** `SlidingMemory.get_context_for_prompt()` 追加历史落子到 prompt 中。随着步数增加，prompt 变长，LLM 响应变慢（token 数增加）。

**影响：** 中后期每步比开局慢 0.5-1 秒。

**修复方案：**

- 严格限制记忆段落的字符数（当前 max_chars=500 已较合理，但可降至 300）。
- 仅传递关键事件（技能触发、威胁出现），不传递每步落子记录。
- 使用摘要而非原始记录（例如 "前5步围绕左下角展开"）。

---

## 瓶颈 7：Model 选择——复杂局面用 qwen-turbo 精度不足可能重试

**现状：** tactical 和 defense 使用 `qwen-turbo`，chief 和 devil 使用 `qwen-plus`。turbo 更快但输出格式不稳定，parse_response 中 fallback 到 `LLMClient.parse_move()` 用正则提取坐标。

**影响：** turbo 的 JSON 格式遵从度较低，偶尔需要 fallback 解析，此时 confidence 被降到 0.3。

**修复方案：**

- 统一使用 `qwen-plus`（更快但稳定的 JSON 输出比偶尔失败的 turbo 总耗时更优）。
- 或在调用 turbo 时强制使用 `response_format="json_object"`（当前已在 `LLMClient.chat` 中设置，但 turbo 对 json_object 的支持不如 plus 稳定）。

---

## 瓶颈 8：Orchestrator 初始化时每个 Agent 创建独立 LLMClient

**现状：** `MultiAgentOrchestrator.__init__()` 中创建 4 个独立的 `LLMClient` 实例，每个都初始化一个 `OpenAI` 客户端。

**影响：** 4 个独立的 HTTP 连接池，内存和连接开销翻倍。

**修复方案：**

- 共享一个 `OpenAI` 客户端实例，各 Agent 的 `LLMClient` 只保存 model 和 temperature 差异。

---

## 瓶颈 9（关键）：LLM 同步调用阻塞主线程，导致 UI 完全冻结

### 现象

- AI 思考期间，棋盘窗口**卡死不动**，无法拖拽、无法重绘
- Windows 标题栏显示 **"（未响应）"**
- 即使 `_draw_board()` 在 AI 调用前执行，`root.update()` 也只能刷出一帧，随后整个进程被 HTTP 请求阻塞
- AI vs AI 模式下，UI 在 **95% 的时间里处于冻结状态**

### 根因

tkinter 是单线程 GUI 框架，所有事件（绘制、点击、定时器）都由主线程的 **事件循环（event loop）** 串行处理：

```
主线程时间线（当前）：
┌──────┬─────────────────────────────────────────┬──────┬──────────────────
│ 刷新  │  HTTP 请求阻塞（6-12秒，事件循环完全停止） │ 刷新  │  下一次 AI 调用的阻塞...
│ UI   │  窗口无法重绘 / 无法响应 / 无法拖动      │ UI   │
└──────┴─────────────────────────────────────────┴──────┴──────────────────
         ↑ 这段时间内 tkinter 事件循环被冻结 ↑
```

具体调用链：

```
root.after(800, self._trigger_ai_move)
  → trigger_ai_move()                          # 在主线程执行
    → orchestrator.analyze(controller)          # 同步阻塞
      → tactical.think()                        # HTTP 请求，阻塞 2-3s
      → defense.think()                         # HTTP 请求，阻塞 2-3s
      → devil_advocate.think()                  # HTTP 请求，阻塞 2-3s
      → chief.think()                           # HTTP 请求，阻塞 2-3s
    → handle_click(x, y)                        # 落子
    → draw_board()                              # 终于刷新 UI
```

### 影响

| 模式 | 冻结频率 | 体验 |
|------|----------|------|
| AI vs AI | 连续冻结，仅落子瞬间刷新 | 完全不可交互，观察体验极差 |
| 人机对战 | 每回合冻结 6-12 秒 | 用户操作后窗口假死，体验割裂 |
| AI 提示 | 点击"AI提示"后冻结 6-12 秒 | 等半天才看到结果 |

### 修复方案

#### 方案 A（推荐）：后台线程 + 轮询

将 LLM 调用移到后台线程，主线程定时检查结果：

```python
import threading

def _trigger_ai_move(self):
    if self._ai_pending:
        return
    self._ai_pending = True
    self._draw_board()
    
    def run_ai():
        result = self._controller.trigger_ai_move()
        self._ai_result = result
        self._ai_done = True
    
    self._ai_result = None
    self._ai_done = False
    thread = threading.Thread(target=run_ai, daemon=True)
    thread.start()
    self._poll_ai_result()  # 每 100ms 检查一次

def _poll_ai_result(self):
    if self._ai_done:
        self._ai_pending = False
        self._draw_board()
        self._refresh_skill_windows()
        if self._ai_result:
            messagebox.showinfo("游戏结束", self._ai_result)
        elif self._is_ai_turn():
            self._root.after(200, self._trigger_ai_move)
    else:
        # 更新思考动画（如闪烁光标、思考时间计数等）
        self._draw_thinking_indicator()
        self._root.after(100, self._poll_ai_result)
```

**优点：**
- UI 完全不卡顿，窗口可自由拖动、重绘
- 可实现"AI 思考中"的动画效果
- 改动量中等，不改变 orchestrator 内部逻辑

**注意点：**
- tkinter 不是线程安全的，**后台线程绝不能直接操作 UI 组件**
- 所有 UI 更新必须在主线程的 `after` 回调中进行
- `GameController` 的 `handle_click` 会修改棋盘状态，需要确认其线程安全性（当前每次只触发一个 AI 调用，没有并发冲突）

#### 方案 B：asyncio + tkinter 集成

利用 orchestrator 已有的 `analyze_async()` 方法，配合 tkinter 的 asyncio 事件循环：

```python
import asyncio
from asyncio import run_coroutine_threadsafe

async def _trigger_ai_move_async(self):
    self._ai_pending = True
    self._draw_board()
    
    result = await self._controller.trigger_ai_move_async()
    
    self._ai_pending = False
    self._draw_board()
    # ...
```

需要 tkinter 支持 asyncio 事件循环（可通过 `tkinter` + `asyncio` 的 event loop 集成实现，如使用 `asyncio.get_event_loop().run_until_complete` 或第三方库 `asynctkinter`）。

**优点：** 复用已有的 async 代码，更现代化。

**缺点：** tkinter 本身不支持 asyncio，需要额外的事件循环桥接代码。

#### 方案 C：Python `multiprocessing` / `concurrent.futures`

使用 `ThreadPoolExecutor` 或 `ProcessPoolExecutor`：

```python
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=1)

def _trigger_ai_move(self):
    future = _executor.submit(self._controller.trigger_ai_move)
    self._root.after(100, self._check_ai_result, future)

def _check_ai_result(self, future):
    if future.done():
        result = future.result()
        # 处理结果...
    else:
        self._root.after(100, self._check_ai_result, future)
```

**优点：** 标准库，代码简洁。

**缺点：** 对异常处理的控制不如手动线程。

### 优先级调整

UI 冻结是**用户直接感知**的最严重问题——即使 AI 思考只需 2 秒，窗口卡死 2 秒也远不如丝滑的 6 秒体验。这个瓶颈应作为 **P0+** 优先修复。

---

## 优先级建议

| 优先级 | 瓶颈 | 预期收益 | 实现难度 |
|--------|------|----------|----------|
| **P0+** | #9 UI 线程阻塞 → 后台线程 | 消除窗口"未响应"，全程可交互 | 中 |
| **P0** | #1 tactical/defense 并行化 | 每步 -2~3s | 中 |
| **P0** | #2 simple 阶段跳过 LLM | 开局每步 -6s | 低 |
| **P1** | #3 减少 after() 延迟 | 每局 -2.5min | 低 |
| **P1** | #4 共识短路 | 每步 -2~3s（约 40% 步数） | 低 |
| **P2** | #5 候选格范围优化 | 每步 -0.1s | 低 |
| **P2** | #8 共享 OpenAI 客户端 | 内存 -3 连接 | 低 |
| **P3** | #6 记忆裁剪 | 中后期每步 -0.5s | 低 |
| **P3** | #7 统一模型 | 减少解析失败 | 低 |

**P0+ 和 P0 四项同时实施后，AI 思考时窗口保持流畅可交互，每步落子耗时从 6-12 秒降至 2-4 秒，整局 AI vs AI 从 30 分钟降至 8-12 分钟，且 UI 全程无卡顿。**
