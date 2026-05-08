# 五子棋 —— 万宁招式·多智能体协作版

> **本项目完全由 Claude Code + DeepSeek V4 Pro 开发。**

基于 tkinter 的五子棋游戏，集成万宁五子棋招式系统（10 种技能）与基于 **LangGraph** 的多智能体 AI 系统。支持双人对战、人机对战、AI vs AI 观战模式，AI 可辅助人类决策。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（AI 相关功能需要）
# Windows PowerShell:
$env:DASHSCOPE_API_KEY = "your-aliyun-bailian-key"
# Linux / macOS:
export DASHSCOPE_API_KEY="your-aliyun-bailian-key"

# 3. 启动
python run_game.py
```

API Key 获取：https://bailian.console.aliyun.com → API Key 管理

---

## 游戏模式

| 模式 | 说明 | AI 角色 |
|------|------|---------|
| 双人对战 | 两人轮流点击落子，各随机分配一个招式 | 不启用 |
| 人机对战（执黑） | 玩家执黑先手，AI 执白后手 | 对手 + 可辅助玩家 |
| 人机对战（执白） | AI 执黑先手，玩家执白后手 | 对手 + 可辅助玩家 |
| **AI vs AI（观战）** | 双方均由多智能体决策 | 双方自动对弈 |

---

## 界面布局

```
┌──────────┐   ┌─────────────────────┐   ┌──────────┐
│ 黑棋招式  │   │                     │   │ 白棋招式  │
│ 面板     │   │    15×15 棋盘        │   │ 面板     │
│          │   │                     │   │          │
│ [使用招式]│   │   状态栏             │   │ [使用招式]│
│ [AI提示] │   │   AI 思考动画        │   │ [AI提示] │
│          │   │                     │   │          │
│ 消息日志  │   │                     │   │ 消息日志  │
└──────────┘   └─────────────────────┘   └──────────┘
```

- **双窗口设计**：黑棋和白棋各有独立的招式面板窗口，分别位于棋盘左右两侧
- **AI 提示按钮**：人机对战中，人类玩家的面板上会显示"AI提示"按钮，点击后多智能体分析局势并在消息日志中给出建议，**最终决策由人类做出**
- **动态思考动画**：AI 思考时棋盘状态栏显示动态动画，窗口全程可交互不卡死

---

## 万宁招式系统（10 种）

每局双方各随机抽取一个招式（确保双方不同）。招式分为**主动**（点击按钮触发）和**被动**（条件自动触发）。

### 主动招式（3 个）

| 招式 | 冷却 | 效果 |
|------|------|------|
| **万宁阵法** | 3 回合 | 在任意空位额外放置 1 子（需点击棋盘选择目标） |
| **血狱影杀阵** | — | 20% 概率在上一落子相邻格生成 1 子 |
| **四方阵** | — | 在上一落子斜向生成 1 子 |

### 被动招式（7 个）

| 招式 | 触发条件 | 效果 |
|------|----------|------|
| **归元阵** | 己方连成 4 子 | 自动生成 1 颗防守棋子 |
| **五雷阵** | 对手释放招式 | 随机清除对手 1 颗技能生成子 |
| **八卦阵** | 每 5 回合（40% 概率） | 转换对手 1 颗边角棋子 |
| **困龙阵** | 对手连续同一直线落子 | 随机封锁 1 个空位 |
| **绝户阵** | 始终生效 | 对手场上最多 3 颗技能生成子 |
| **克敌先机** | 对手连成 4 子 | 自动补 1 颗卡位棋子 |
| **梅花阵** | 每 4 回合 | 生成 1 颗花苞，格挡对手 1 次落子 |

---

## 多智能体 AI 架构

### 整体架构

```
GameController ──→ GameInfoExtractor ──→ MultiAgentOrchestrator (LangGraph)
                                              │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
              ┌─────▼─────┐            ┌──────▼──────┐           ┌──────▼──────┐
              │  战术官    │            │   防守官     │           │  反对官      │
              │ (qwen-turbo)│           │ (qwen-turbo) │           │ (qwen-plus) │
              │  进攻分析   │            │   防守分析    │           │  压力测试    │
              └─────┬─────┘            └──────┬──────┘           └──────┬──────┘
                    │                          │                          │
                    └──────────────────────────┼──────────────────────────┘
                                               │
                                        ┌──────▼──────┐
                                        │  总策划官    │
                                        │ (qwen-plus) │
                                        │  汇总裁决    │
                                        └──────┬──────┘
                                               │
                                        最终落子 (x, y)
```

### LangGraph 图流程（优化版）

```
START → phase_check
         ├─ simple/emergency → engine_fallback → END     (跳过 LLM，引擎直出)
         └─ normal/complex  → Send("tactical") ║ Send("defense")   (并行)
                                    ↓                    ↓
                               post_analysis ← post_analysis        (join 屏障)
                                          ↓
                              ┌─ 共识 → consensus → END    (跳过 chief)
                              ├─ complex → devil → chief → END
                              └─ normal → chief → END
```

### 四个智能体

| 角色 | 模型 | 职责 |
|------|------|------|
| **战术官** TacticalAnalyst | qwen-turbo | 寻找进攻机会，结合己方招式优化策略 |
| **防守官** DefenseSpecialist | qwen-turbo | 识别对手威胁，结合敌方技能做风险预警 |
| **反对官** DevilAdvocate | qwen-plus | 对战术官和防守官的提案进行压力测试（仅复杂局） |
| **总策划官** ChiefStrategist | qwen-plus | 汇总所有意见，做出最终落子裁决 |

### 性能优化

| 优化项 | 说明 |
|--------|------|
| **LangGraph Send fan-out** | tactical 和 defense 通过 LangGraph 原生 `Send` API 并行执行 |
| **局势分级跳过 LLM** | simple（无威胁）和 emergency（对手四连）直接使用引擎，0 次 LLM 调用 |
| **共识短路** | tactical 和 defense 建议相同落子且置信度 > 0.8 时，跳过 chief |
| **后台线程** | LLM 调用在后台线程执行，主线程不阻塞，UI 全程流畅 |
| **引擎候选预过滤** | 每步计算 Top-8 候选格提供给 LLM 作为参考 |
| **滑动窗口记忆** | 短时记忆（10 步）+ 长时记忆（5 事件），控制在 500 字符内 |

---

## 项目结构

```
├── run_game.py                  # 启动入口
├── requirements.txt             # 依赖清单
│
├── 五子棋/                      # 游戏核心
│   ├── core/
│   │   ├── constants.py         # 棋盘常量、颜色、尺寸
│   │   ├── models.py            # Board / Player / Position / SkillResult
│   │   └── controller.py        # GameController（状态机 + AI 接口）
│   ├── skills/
│   │   ├── base.py              # Skill 基类 + SkillType 枚举
│   │   └── definitions.py       # 10 个招式实现 + 随机分配
│   └── ui/
│       ├── game_window.py       # 主窗口（棋盘 + 模式选择 + 后台AI线程）
│       └── skill_window.py      # 单玩家招式面板（技能 + AI提示按钮）
│
├── agent/                       # AI 多智能体系统
│   ├── engine.py                # 启发式评分引擎（兜底策略）
│   ├── board_codec.py           # 棋盘 ↔ 文本 编解码
│   ├── llm_client.py            # DashScope LLM 调用客户端
│   ├── logger.py                # 日志系统（文件 + 控制台）
│   ├── core/
│   │   ├── orchestrator.py      # LangGraph StateGraph 编排器（Send fan-out）
│   │   ├── state.py             # MultiAgentState 图状态定义
│   │   └── protocol.py          # Proposal / Critique / FinalDecision 协议
│   ├── agents/
│   │   ├── base_agent.py        # Agent 抽象基类（模板方法）
│   │   ├── tactical_analyst.py  # 战术官（进攻分析）
│   │   ├── defense_specialist.py# 防守官（防守分析）
│   │   ├── devil_advocate.py    # 反对官（压力测试）
│   │   └── chief_strategist.py  # 总策划官（最终裁决）
│   ├── game_info/
│   │   └── extractor.py         # 游戏信息提取器（生成 game_report）
│   ├── memory/
│   │   └── sliding_memory.py    # 双层滑动窗口记忆
│   ├── speed/
│   │   └── speed_controller.py  # 局势分级 + 超时控制
│   └── prompts/                 # 角色提示词模板
│       ├── tactical.txt
│       ├── defense.txt
│       ├── devil_advocate.txt
│       └── chief.txt
│
├── 万宁五子棋招式.md             # 招式设计文档
├── AI_vs_AI性能分析.md           # 性能瓶颈分析
└── AI_vs_AI性能修复报告.md       # 性能修复报告
```

---

## 依赖

```
langgraph >= 0.2.0
langchain-core >= 0.3.0
openai >= 1.0.0
```

Python 标准库：`tkinter`, `abc`, `dataclasses`, `enum`, `typing`, `collections`, `re`, `os`, `json`, `asyncio`, `random`, `threading`, `concurrent.futures`

---

## 设计原则

- **OOP 单一职责**：一个文件一个核心类，封装行为，接口交互
- **高内聚低耦合**：Agent 之间互不知晓，仅通过 LangGraph State 传递信息
- **LangGraph 原生**：并行、路由、状态管理全部由 LangGraph 框架处理
- **线程安全**：LLM 调用在后台线程执行，UI 更新全部在主线程回调中完成
- **渐进式 AI**：简单局用引擎，复杂局用多智能体，共识时自动短路

---

## 版本历史

### v0.1.1 (2026-05-08)

- 修复：梅花阵"花苞"效果现在可在棋盘上正确显示（粉色花苞标记）
- 棋盘上被封锁的位置（花苞 / 困龙阵封锁格）现在会以粉色圆形标记渲染

### v0.1.0 (2026-05-07)

- 初始版本：15×15 五子棋游戏，集成 10 种万宁招式
- 基于 LangGraph 的多智能体 AI 系统（战术官 + 防守官 + 反对官 + 总策划官）
- 双人对战、人机对战、AI vs AI 观战模式
- 双窗口招式面板设计
- AI 提示辅助功能
