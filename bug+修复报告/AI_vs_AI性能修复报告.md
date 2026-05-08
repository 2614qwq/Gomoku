# AI vs AI 性能修复报告

> 修复日期：2026-05-08
> 基于：`AI_vs_AI性能分析.md` 瓶颈 #1, #2, #3, #4, #9

---

## 修复总览

| 修复项 | 优先级 | 状态 |
|--------|--------|------|
| #9 UI 线程阻塞 → 后台线程 | P0+ | ✅ 完成 |
| #1 tactical/defense 并行化 | P0 | ✅ 完成 |
| #2 simple 阶段跳过 LLM | P0 | ✅ 完成 |
| #3 减少 after() 延迟 | P1 | ✅ 完成 |
| #4 共识短路 | P1 | ✅ 完成 |

---

## 修复详情

### 修复 #9：LLM 调用移至后台线程，消除 UI 冻结

**文件：** `五子棋/ui/game_window.py`

**改动：**
- `_trigger_ai_move()` 不再直接调用 `controller.trigger_ai_move()`，而是将其提交到 `threading.Thread` 后台线程
- 新增 `_poll_ai_result(holder)` 方法，通过 `root.after(100)` 每 100ms 轮询结果
- AI 思考期间，主线程持续运行 tkinter 事件循环，窗口可自由拖动、重绘
- 新增 `_draw_thinking_indicator()` 在棋盘上显示动态思考动画（`AI 思考中.` → `AI 思考中..` → `AI 思考中...`）
- AI 分析结果（`_on_ai_analysis`）延迟到主线程的轮询回调中执行，避免 tkinter 线程安全问题
- `_request_ai_hint()` 同样使用后台线程 + 轮询模式

**关键设计决策：**
- 使用 `dict` 作为结果容器（`holder = {"data": None, "error": None}`），后台线程写入，主线程读取
- CPython GIL 保证了简单赋值的原子性，无需额外锁
- 主线程绝不阻塞等待，始终保持事件循环运行

**效果：**
- **修复前：** AI 思考期间窗口完全卡死，Windows 显示"（未响应）"
- **修复后：** AI 思考期间窗口流畅可交互，显示动态思考动画

---

### 修复 #1：tactical 与 defense 并行执行（LangGraph Send fan-out）

**文件：** `agent/core/orchestrator.py`、`agent/core/state.py`

**改动：**
- 恢复独立的 `_tactical_node` 和 `_defense_node` 作为 LangGraph 独立节点
- 使用 **LangGraph 原生 `Send` API** 实现 fan-out：`phase_check` 返回 `[Send("tactical", state), Send("defense", state)]`，两个节点由 LangGraph 框架并行调度
- 新增 `_post_analysis_node` 作为 join 节点，使用 `_join_counter` 计数器实现屏障同步，确保两个 Agent 都完成后才继续
- `_route_after_join` 在 join 之后根据结果路由到共识/反对官/总策划官
- state 新增 `_join_counter: int` 字段

**LangGraph 图结构：**
```
START → phase_check
         ├─ (skip_llm) → engine_fallback → END
         └─ (analyze) → Send("tactical") ║ Send("defense")   ← LangGraph 原生并行
                              ↓                    ↓
                         post_analysis ← post_analysis        ← join 屏障
                                    ↓
                         (consensus / devil / chief)
                                    ↓
                                   END
```

**关键技术细节：**
- `Send` 是 LangGraph `>=0.2.0` 的标准 API，每个 `Send` 对象指定目标节点和初始 state
- tactical 写 `tactical_proposal`，defense 写 `defense_proposal`——不同 key，无冲突
- `post_analysis` 被两条边连接，使用 `_join_counter` 保证第二次到达时才执行实际路由
- 每个 Agent 持有独立的 `LLMClient` 实例（qwen-turbo），线程安全

**效果：**
- **修复前：** tactical (2-3s) + defense (2-3s) = 串行 4-6s
- **修复后：** max(tactical, defense) ≈ 2-3s，每步节省 2-3s

---

### 修复 #2：simple 阶段跳过 LLM，直接使用引擎

**文件：** `agent/core/orchestrator.py`

**改动：**
- `_phase_check_node` 中将 `skip_llm` 的条件从 `phase == "emergency"` 扩展为 `phase in ("emergency", "simple")`
- `_engine_fallback_node` 根据 phase 生成不同描述（"简单局面" / "紧急防守" / "快速决策"）

**局势分级逻辑（`speed_controller.py`，未修改）：**
| 局面 | 条件 | LLM |
|------|------|-----|
| emergency | 对方有四连 | 跳过 → 引擎 |
| simple | 无任何三连/四连威胁 | 跳过 → 引擎（新增） |
| normal | 有 1-2 个威胁 | 走 LLM 流程 |
| complex | ≥3 个威胁 | 走完整 LLM 流程（含反对官） |

**效果：**
- **修复前：** 开局及简单中盘每步 3 次 LLM 调用（~6s）
- **修复后：** 开局及简单中盘每步 0 次 LLM 调用（~0.1s 引擎计算），速度提升约 60 倍

---

### 修复 #3：减少 AI vs AI 的人为延迟

**文件：** `五子棋/ui/game_window.py`

**改动：**
- AI vs AI 循环：`root.after(800, ...)` → `root.after(200, ...)`
- 人类落子后触发 AI：`root.after(300, ...)` → `root.after(200, ...)`
- 200ms 足够 UI 完成刷新（tkinter Canvas 重绘通常在 <16ms 内完成）

**效果：**
- **修复前：** 每步额外 800ms 等待，200 步共 160 秒
- **修复后：** 每步 200ms，200 步共 40 秒，节省 2 分钟

---

### 修复 #4：tactical 与 defense 共识时跳过 chief

**文件：** `agent/core/orchestrator.py`

**改动：**
- 新增 `_consensus_node`：当 tactical 和 defense 推荐相同落子且 confidence 均 > 0.8 时，直接作为最终决策
- 新增 `_route_after_analysis` 条件路由：
  - 共识达成 → `consensus` → END（跳过 chief LLM 调用）
  - complex 阶段 → `devil` → `chief` → END
  - normal 阶段 → `chief` → END

**效果：**
- **修复前：** 即使两名 Agent 完全同意，仍需 chief 再调一次 LLM
- **修复后：** 共识场景直接采纳，节省 1 次 LLM 调用（约 2-3s）
- 预期约 30-40% 的步数触发共识短路

---

## 性能对比

### 每步 AI 落子耗时

| 局面 | 修复前 | 修复后 | 提升 |
|------|--------|--------|------|
| 开局（空棋盘） | ~6s（3次LLM串行） | ~0.1s（引擎） | **60x** |
| 简单中盘 | ~6s（3次LLM串行） | ~0.1s（引擎） | **60x** |
| 正常局面 | ~6-8s（3次LLM串行） | ~2-5s（并行+可能共识短路） | **~2x** |
| 复杂局面 | ~10-12s（4次LLM串行） | ~5-8s（并行+反对官+chief） | **~1.5x** |
| 共识局面 | ~6-8s | ~2-3s（并行，跳过chief） | **~3x** |

### 整局 AI vs AI（200步）

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 总耗时（估算） | ~30分钟 | **~8-12分钟** |
| after() 等待累计 | 160s | 40s |
| simple 阶段步数（~60步） | 360s | 6s |
| UI 响应性 | 95%时间冻结 | 全程流畅可交互 |

---

## 修改文件清单

| 文件 | 改动类型 |
|------|----------|
| `agent/core/state.py` | 新增 `_join_counter` 字段 |
| `agent/core/orchestrator.py` | 重构（Send fan-out + join屏障 + simple跳过 + 共识短路） |
| `五子棋/core/controller.py` | 修改 `trigger_ai_move()` 返回类型（str → dict） |
| `五子棋/ui/game_window.py` | 重构（后台线程 + 轮询 + 动画 + 减延迟） |

---

## 验证结果

```
=== Test 1: LangGraph Send API ===
Send import OK

=== Test 2: Graph structure ===
Nodes: ['__start__', 'phase_check', 'engine_fallback', 'tactical', 'defense',
        'post_analysis', 'devil_advocate', 'chief', 'consensus', '__end__']
All expected nodes present

=== Test 3: Fan-out logic ===
skip_llm=True → "engine_fallback" OK
skip_llm=False → [Send("tactical"), Send("defense")] OK

=== Test 4: Simple phase → engine fallback ===
Simple phase: 0.04s, move=(7, 7), reason="引擎简单局面"
→ 0 LLM calls ✓

=== Test 5: Non-simple phase → LLM fan-out ===
Moves placed: 9 (threats created)
tactical: move=(8, 9), confidence=0.90
defense:  move=(8, 9), confidence=0.95
→ 检测到共识: (8, 9), 跳过总策划官
Elapsed: 2.8s (vs 4-6s serial)
→ 2 parallel LLM calls, consensus shortcut activated ✓

All tests passed!
```

- 所有修改文件 Python 语法检查通过
- LangGraph `Send` fan-out 正确生成并行分支
- `_join_counter` 屏障同步正确（post_analysis 在双方完成后才路由）
- simple/emergency 阶段正确跳过 LLM（0.04s 引擎兜底）
- 共识短路正确触发（tac + def 一致且 confidence > 0.8 时跳过 chief）

---

## 未修复项（后续优化）

| 瓶颈 | 说明 |
|------|------|
| #5 候选格范围优化 | 收益较小（每步 0.1s），且引擎+LLM并行后影响有限 |
| #6 记忆裁剪 | 当前 max_chars=500 已合理，后期优化 |
| #7 统一模型 | 当前 turbo/plus 分工合理，未发现频繁解析失败 |
| #8 共享 OpenAI 客户端 | 内存优化，非速度瓶颈 |
