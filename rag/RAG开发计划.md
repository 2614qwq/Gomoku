# 五子棋 RAG 知识检索 —— 开发计划

**目标**：将棋谱 CSV + 未来文字资料统一入库 Chroma，战术官/防守官通过 tool-calling 检索。

**扩展预留**：后续可添加文字资料（定式讲解、策略文章等），统一经 `Indexer` → `Retriever` → `Tool` 三层管道处理。

---

## 1. 架构设计（高内聚低耦合）

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent (tool-calling)                    │
│  战术官 / 防守官  →  chat_with_tools()  →  execute_tool()   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Tool 层
┌──────────────────────────────▼──────────────────────────────┐
│  rag/tools.py                    Tool Registry               │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ search_openings │  │ search_materials│ ← 未来扩展        │
│  └────────┬────────┘  └────────┬────────┘                   │
└───────────┼────────────────────┼────────────────────────────┘
            │                    │
┌───────────▼────────────────────▼────────────────────────────┐
│  rag/retriever.py                Retriever 层                │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │OpeningRetriever  │  │MaterialRetriever │ ← 未来扩展      │
│  │ (棋谱相似检索)    │  │ (全文语义检索)    │                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
│           │      继承            │                           │
│           └────── BaseRetriever ─┘                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  rag/embedder.py                Embedding 层                 │
│  调用 text-embedding-v4，统一入口                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  rag/indexer.py                 Indexer 层                   │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ChessRecordIndexer│  │TextDocIndexer    │ ← 未来扩展      │
│  │ (CSV棋谱入库)     │  │ (文字资料入库)    │                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
│           │      继承            │                           │
│           └────── BaseIndexer ───┘                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 ChromaDB (gomoku_knowledge)                  │
│  doc_type: "chess_record" | "text_material"                 │
└─────────────────────────────────────────────────────────────┘
```

### 分层职责

| 层 | 文件 | 职责 | 对外接口 |
|----|------|------|----------|
| **Embedding** | `embedder.py` | 封装 text-embedding-v4 API | `embed(text)` / `embed_batch(texts)` |
| **Indexer** | `indexer.py` | 读取数据源 → 生成文档 → 写入 ChromaDB | `BaseIndexer.index()` |
| **Retriever** | `retriever.py` | ChromaDB 查询 + 结果格式化 | `BaseRetriever.search(query)` |
| **Tools** | `tools.py` | Tool schema 定义 + 执行分发 | `ToolRegistry.execute(name, args)` |
| **__init__** | `__init__.py` | 统一导出，懒加载初始化 | `get_retriever()` / `get_tools()` |

---

## 2. ChromaDB 设计

### Collection: `gomoku_knowledge`

统一存储棋谱 + 文字资料，通过 `doc_type` 字段区分：

| 字段 | 说明 |
|------|------|
| `id` | `{doc_type}:{unique_id}` |
| `document` | 用于 embedding 的文本 |
| `embedding` | text-embedding-v4 1024 维向量 |
| `metadata.doc_type` | `chess_record` / `text_material` |
| `metadata.source` | 来源标识（文件名/md5） |
| `metadata.display_text` | 给 LLM 看的完整文本（不参与 embedding） |

---

## 3. 文件规划

```
rag/
├── __init__.py              # 统一入口、懒加载单例
├── embedder.py              # Embedding API 封装
├── indexer.py               # 基类 + ChessRecordIndexer (+ 未来 TextDocIndexer)
├── retriever.py             # 基类 + OpeningRetriever (+ 未来 MaterialRetriever)
├── tools.py                 # Tool 注册表 + 执行函数
├── build_index.py           # CLI 入口：python -m rag.build_index
└── RAG开发计划.md            # 本文件
```

### 需修改的现有文件

| 文件 | 改动 |
|------|------|
| `agent/llm_client.py` | 新增 `chat_with_tools()` |
| `agent/agents/base_agent.py` | 新增 `think_with_tools()` (泛化，不写死 RAG) |
| `agent/core/orchestrator.py` | 初始化 RAG，节点中注入检索上下文 |
| `agent/game_info/extractor.py` | 新增 `_rag_section()` |

---

## 4. 分步任务

### 阶段一：基础设施（`embedder.py` + `indexer.py` + `build_index.py`）

**Task 1**: 创建 `rag/embedder.py`
- `Embedder` 类封装 text-embedding-v4
- `embed(text: str) -> list[float]`
- `embed_batch(texts: list[str]) -> list[list[float]]`
- 内置速率控制（sleep 0.2s/batch）

**Task 2**: 创建 `rag/indexer.py`
- `BaseIndexer(ABC)` — 抽象基类，定义 `index(collection) -> int`
- `ChessRecordIndexer` — 读取 CSV，多粒度切分（open3/5/10/full），写入 ChromaDB
- 通过 `metadata.doc_type = "chess_record"` 标记
- 内置 md5 增量检测

**Task 3**: 创建 `rag/build_index.py`
- CLI 脚本：`python -m rag.build_index [--force]`
- 连接 ChromaDB → 创建 collection → 调用 Indexer
- 输出统计：`入库 N 条 | 跳过 M 条 | 耗时 Xs`

### 阶段二：检索（`retriever.py`）

**Task 4**: 创建 `rag/retriever.py`
- `BaseRetriever(ABC)` — 定义 `search(query, top_k) -> list[Result]`
- `OpeningRetriever` — 将当前棋盘前N手转为 query_text → embed → ChromaDB.query → 格式化
- `Result` dataclass: `(id, document, metadata, distance)`
- `format_context(results) -> str` — 转为 LLM 可读的【棋谱参考】段落

### 阶段三：Tool-Calling（`tools.py` + 现有文件改造）

**Task 5**: 创建 `rag/tools.py`
- `ToolRegistry` — 注册/查找/执行工具的注册表
- 注册 `search_chess_openings` tool（schema + handler）
- `execute_tool(name, args) -> str` 统一入口

**Task 6**: 改造 `agent/llm_client.py`
- 新增 `chat_with_tools(system_prompt, user_message, tools)` 方法
- 返回 `ChatCompletionMessage`（含 `tool_calls` 属性）

**Task 7**: 改造 `agent/agents/base_agent.py`
- 新增 `think_with_tools(game_report, tools, tool_executor)` — 泛化的 tool-calling 循环
- 不硬编码 RAG 逻辑；tool 定义和 handler 由外部注入

### 阶段四：集成 + 测试

**Task 8**: 修改 `agent/core/orchestrator.py`
- `__init__` 中懒加载 RAG retriever + tools
- tactical/defense 节点使用 `think_with_tools()` 替代 `think()`
- game_report 通过 extractor 追加检索上下文

**Task 9**: 修改 `agent/game_info/extractor.py`
- 新增 `build_game_report_with_rag(rag_context)` 方法
- 已有 `build_game_report()` 保持不变（向后兼容）

**Task 10**: 端到端测试 + README 更新

---

## 5. 扩展点设计

后续添加文字资料时，只需：

1. 创建 `TextDocIndexer(BaseIndexer)` — 读 txt/md → 分块 → embed → 写入（`doc_type="text_material"`）
2. 创建 `MaterialRetriever(BaseRetriever)` — 全文语义搜索
3. 在 `ToolRegistry` 中注册新 tool：`search_strategy_materials`
4. 无需改动 Embedder / BaseRetriever / ToolRegistry / Agent 代码

---

## 6. 注意事项

- 各层之间通过接口（抽象基类）通信，不直接依赖具体实现
- `rag/__init__.py` 提供懒加载单例，避免多处实例化 ChromaDB client
- 嵌入 API 速率控制放在 Embedder 层，上层无需关心
- Tool 的 schema 和 handler 在注册表中绑定，Agent 只依赖 `ToolRegistry.execute(name, args)` 接口
