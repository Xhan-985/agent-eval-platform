# AgentEval 开发交接文档

> 面向：开发工程师 / Codex / Claude Code
> 阶段：Week 1（采集 SDK + 教学注释）
> 约束：本文档不含实现代码，仅含接口契约与数据结构

---

## 1. 项目目录结构

```
agenteval/
├── agenteval/                    # 主包
│   ├── __init__.py               # 对外 API：init(), @trace
│   ├── collector/                # 采集层（Week 1 实现）
│   │   ├── __init__.py
│   │   ├── callback.py           # AgentEvalCallbackHandler
│   │   ├── annotator.py          # 教学注释生成器
│   │   └── serializer.py         # trace 树构建 + JSON 序列化
│   ├── storage/                  # 存储层（Week 2 实现）
│   │   ├── __init__.py
│   │   ├── db.py                 # SQLite CRUD
│   │   └── schema.py             # 表结构定义
│   ├── replay/                   # replay 层（Week 4 实现）
│   │   ├── __init__.py
│   │   ├── runner.py             # 安全 replay 引擎
│   │   └── policy.py             # replay 策略
│   └── web/                      # 展示层（Week 2-4 实现）
│       ├── __init__.py
│       ├── app.py                # Streamlit 主入口
│       ├── list_view.py          # trace 列表页
│       ├── trace_view.py         # 树状图 + 注释
│       └── replay_view.py        # replay 面板
├── examples/                     # 示例
│   └── react_agent_trace.py      # ReAct Agent 完整示例
├── tests/                        # 测试
│   ├── test_callback.py
│   ├── test_serializer.py
│   └── test_annotator.py
├── README.md
├── pyproject.toml                # 包配置
└── .python-version               # 3.12
```

### 当前阶段需创建的文件

Week 1 只实现以下文件，其余模块创建空 `__init__.py` 占位：

| 文件 | 状态 | 说明 |
|------|------|------|
| `agenteval/__init__.py` | ✅ 实现 | 对外 API |
| `agenteval/collector/__init__.py` | ✅ 实现 | 模块导出 |
| `agenteval/collector/callback.py` | ✅ 实现 | callback handler |
| `agenteval/collector/annotator.py` | ✅ 实现 | 注释生成 |
| `agenteval/collector/serializer.py` | ✅ 实现 | trace 序列化 |
| `agenteval/storage/__init__.py` | 占位 | Week 2 |
| `agenteval/replay/__init__.py` | 占位 | Week 4 |
| `agenteval/web/__init__.py` | 占位 | Week 2 |
| `examples/react_agent_trace.py` | ✅ 实现 | 端到端示例 |
| `tests/test_callback.py` | ✅ 实现 | 单元测试 |
| `tests/test_serializer.py` | ✅ 实现 | 单元测试 |
| `tests/test_annotator.py` | ✅ 实现 | 单元测试 |
| `pyproject.toml` | ✅ 实现 | 包配置 |

---

## 2. 每个模块的职责

### 2.1 `agenteval/__init__.py` — 对外 API 层

**职责**：暴露用户接入 API，封装内部实现。

**对外接口**：

```
init(db_path: str = "agenteval.db", verbose: bool = False) -> None
    初始化 AgentEval。创建 callback handler 实例，存到模块级变量。
    Week 1 不实际写数据库，db_path 仅记录。

wrap(graph: Runnable) -> Runnable
    包装 LangGraph graph，返回注入了 callback 的新 graph。
    用户直接对返回值调用 .invoke() 即可，无需手动传 config。
    推荐 API，3 行代码接入。

trace(func: Callable) -> Callable
    装饰器。仅适用于签名包含 **kwargs 的函数（会向其传入 callbacks）。
    若函数签名不接受额外参数，请改用 wrap()。
```

**设计约束**：
- `init()` 必须可重复调用（幂等），不报错
- `wrap()` 返回的 graph 调用 `.invoke()` 时自动注入 callback，用户无需关心 config
- `@trace` 仅用于函数签名已包含 `**kwargs` 的场景；优先推荐 `wrap()`
- 被包装的 graph/函数若抛异常，trace 仍需记录 error span，异常向上抛
- callback handler 采集失败不能影响 Agent 执行（try-except 兜底）

**`wrap()` 契约细节**：
- 用户调用包装对象时若同时传 `config`，必须与注入的 `{"callbacks": [...]}` **合并**（保留 `thread_id` 等用户配置），不能覆盖
- Week 1 只实现同步 `invoke`；调用 `ainvoke` / `stream` / `astream` 时抛 `NotImplementedError` 并提示限制
- `init()` 必须先于 `wrap()` 调用；wrap 时绑定当前 handler 实例
- 必须调用返回的包装对象；直接调用原 graph 不会采集 trace

### 2.2 `agenteval/collector/callback.py` — 采集器

**职责**：实现 LangChain `BaseCallbackHandler`，接收 LangGraph 执行事件。

**对外接口**：

```
class AgentEvalCallbackHandler(BaseCallbackHandler):
    def __init__(self, verbose: bool = False) -> None
    # 返回采集到的完整 trace（Agent 执行结束后调用）
    def get_trace() -> dict
    # 重置状态，准备下一次采集
    def reset() -> None
```

**需实现的 BaseCallbackHandler 方法**：

| 方法 | 触发时机 | 采集内容 |
|------|---------|---------|
| `on_chain_start(serialized, inputs, *, run_id, parent_run_id, **kwargs)` | graph node 开始 | span_id, parent_id, name, input, started_at |
| `on_chain_end(outputs, *, run_id, parent_run_id, **kwargs)` | graph node 结束 | output, ended_at |
| `on_chain_error(error, *, run_id, parent_run_id, **kwargs)` | node 出错 | error 信息, ended_at |
| `on_llm_start(serialized, prompts, *, run_id, parent_run_id, **kwargs)` | LLM 调用开始 | model name, messages, invocation params |
| `on_llm_end(response, *, run_id, parent_run_id, **kwargs)` | LLM 调用结束 | output text, token_usage |
| `on_tool_start(serialized, input_str, *, run_id, parent_run_id, **kwargs)` | tool 调用开始 | tool name, input |
| `on_tool_end(output, *, run_id, parent_run_id, **kwargs)` | tool 调用结束 | output |

**内部状态**：
- `self._states: dict[str, SpanState]`：run_id → span 上下文
- `self._children: dict[str, list[str]]`：parent_run_id → [child_run_id]
- `self._root_run_id: str | None`：顶层 run_id

### 2.3 `agenteval/collector/annotator.py` — 注释生成器

**职责**：为每个 span 生成教学化中文注释。

**对外接口**：

```
def annotate(span: dict) -> str
    输入：一个 span dict（含 type, name, input, output, error 等字段）
    输出：1-2 句中文注释字符串
```

**span 类型与注释规则**：

| span type | 注释要点 |
|-----------|---------|
| `agent_run`（顶层） | "这是 Agent 的一次完整执行，目标是 [从 input 提取]" |
| `node` | "Agent 进入 [name] 节点，[根据 name 解释作用]" |
| `llm_call` | "Agent 调用 [model] 决定下一步，[从 output 提取决策结果]" |
| `tool_call` | "Agent 调用 [tool_name]，[从 input 提取参数]，返回 [output 摘要]" |
| `error` | "⚠️ 出错：[error message]。可能原因：[常见原因]" |

**设计约束**：
- 纯函数，无副作用，无状态
- 注释不超过 100 字
- output 摘要截断到 50 字
- 无法识别的字段用通用注释"Agent 执行了一步操作"

### 2.4 `agenteval/collector/serializer.py` — 序列化器

**职责**：把 callback 采集的扁平事件组装成嵌套 trace JSON。

**对外接口**：

```
def build_trace(handler: AgentEvalCallbackHandler) -> dict
    输入：采集完成的 handler 实例
    输出：完整 trace JSON dict（结构见第 5 节）

def serialize_to_json(trace: dict) -> str
    输入：trace dict
    输出：JSON 字符串（ensure_ascii=False, indent=2）
```

**职责边界**：
- 只负责组装和序列化，不负责注释生成（注释由 annotator 生成）
- 但 `build_trace` 内部会调用 `annotator.annotate` 为每个 span 填充 `annotation` 字段

### 2.5 模块间依赖（当前阶段）

```
__init__.py
    ↓ 依赖
callback.py（AgentEvalCallbackHandler）
    ↓ 被调用
serializer.py（build_trace）
    ↓ 调用
annotator.py（annotate）
```

**关键约束**：
- `annotator.py` 不依赖任何其他模块（纯函数）
- `serializer.py` 依赖 `annotator.py` 和 `callback.py`
- `callback.py` 不依赖 `serializer.py` 和 `annotator.py`（只采集，不组装）
- `__init__.py` 依赖以上三者

---

## 3. 模块之间如何通信

### 3.1 通信方式：函数调用（同进程）

Week 1 所有模块在同一进程内，通过直接函数调用通信。不引入消息队列、事件总线、HTTP。

### 3.2 数据流

**采集流**（Agent 运行时）：

```
LangGraph 执行
    → callback.py 的 on_*_start 方法接收事件
    → 存入 self._states[run_id]
    → on_*_end 方法接收事件
    → 更新 self._states[run_id]
    → 记录 parent-child 关系到 self._children
```

**组装流**（Agent 结束后）：

```
__init__.py 的 @trace 装饰器
    → 调用 serializer.build_trace(handler)
    → serializer 从 handler._states 和 handler._children 构建树
    → 对每个 span 调用 annotator.annotate(span) 生成注释
    → 返回完整 trace dict
    → __init__.py 打印或保存 trace
```

### 3.3 接口契约

**`__init__.py` 调用 `callback.py`**：
```
handler = AgentEvalCallbackHandler(verbose=True)
# 把 handler 传入 graph.invoke(config={"callbacks": [handler]})
# Agent 执行结束后：
trace = serializer.build_trace(handler)
```

**`serializer.py` 调用 `annotator.py`**：
```
for span in all_spans:
    span["annotation"] = annotator.annotate(span)
```

**`serializer.py` 读取 `callback.py` 状态**：
```
handler._states   # dict[run_id, SpanState]
handler._children # dict[parent_run_id, list[run_id]]
handler._root_run_id  # str
```

> 注意：`_states` 和 `_children` 是下划线前缀的"私有"属性，serializer 需要直接访问。这是约定的内部接口，不对外暴露。

---

## 4. 当前阶段需要实现的功能

Week 1 需实现以下 5 个功能：

| 编号 | 功能 | 优先级 | 模块 |
|------|------|--------|------|
| F1 | LangGraph 事件采集 | P0 | callback.py |
| F2 | trace 树形结构构建 | P0 | serializer.py |
| F3 | 教学注释生成 | P0 | annotator.py |
| F4 | 3 行代码接入 API | P0 | __init__.py |
| F5 | 端到端示例 | P1 | examples/ |

**不实现**：
- SQLite 存储（Week 2）
- Web 界面（Week 2-3）
- replay（Week 4）
- 诊断 Agent（V2）

---

## 5. 每个功能的输入和输出

### 5.1 数据结构定义

#### SpanState（callback 内部状态）

```
SpanState = {
    span_id: str          # run_id 的字符串形式
    parent_id: str | None # parent_run_id，顶层为 None
    type: str             # "agent_run" | "node" | "llm_call" | "tool_call"
    name: str             # span 名称（从 serialized 提取）
    input: dict | str     # 输入
    output: dict | str    # 输出（end 时填充）
    error: str | None     # 错误信息（error 时填充）
    started_at: str       # ISO 8601 时间戳
    ended_at: str | None  # ISO 8601 时间戳
    metadata: dict        # 额外信息：token_usage、model_name、完整 messages、
                          # invocation params（replay 必需）、tool name/args
}
```

#### Trace JSON（最终输出）

```
Trace = {
    trace_id: str         # UUID
    created_at: str       # ISO 8601
    status: str           # "success" | "error"
    framework: str        # 固定 "langgraph"
    agent_name: str       # 从顶层 span 的 name 提取
    root_span: Span       # 嵌套结构
}

Span = {
    span_id: str
    type: str             # "agent_run" | "node" | "llm_call" | "tool_call"
    name: str
    input: dict | str
    output: dict | str
    error: str | None
    annotation: str       # 教学注释（annotator 生成）
    started_at: str
    ended_at: str
    metadata: dict        # token_usage / invocation_params / tool_call_id / langgraph_node（replay 数据）
    children: [Span]      # 子 span 列表（递归）
}
```

### 5.2 功能 F1：事件采集

**输入**：LangGraph 通过 callback 机制传入的事件参数
```
on_chain_start(serialized: dict, inputs: dict, *, run_id: UUID, parent_run_id: UUID | None, **kwargs)
```

**输出**：更新 `handler._states[run_id]`

**span type 映射规则**：
- `on_chain_start` + `parent_run_id is None` → `type = "agent_run"`
- `on_chain_start` + `parent_run_id is not None` → `type = "node"`
- `on_llm_start` → `type = "llm_call"`
- `on_tool_start` → `type = "tool_call"`

**replay 数据采集（Week 4 前置，必须现在做）**：
- LLM span：metadata 必须包含 `model_name`、完整 `messages`、`invocation_params`（temperature / max_tokens / 工具定义）
- tool span：metadata 包含 tool name、参数，output 字段保存返回结果
- 缺少上述字段，Week 4 replay 无法对历史 trace 重跑，只能改采集契约或放弃 replay

**name 提取规则**：
- 从 `serialized["name"]` 提取
- LLM span 从 `serialized["name"]` 提取模型名（如 "ChatOpenAI"）或 `serialized.get("id", [])` 最后一个元素
- 若提取失败，用 type 作为 name

### 5.3 功能 F2：trace 树构建

**输入**：`handler._states` 和 `handler._children`

**输出**：Trace JSON dict

**构建算法**：
1. `root_run_id = handler._root_run_id`
2. 从 `root_run_id` 开始递归构建
3. 每个 span 的 `children` 从 `handler._children[span_id]` 获取
4. 递归构建子 span
5. 对每个 span 调用 `annotator.annotate` 填充 `annotation`

**边界处理**：
- `output` 为空时填 `null`
- `input`/`output` 若为 LangGraph state 对象，转成 dict（用 `dict()` 或手动转换）
- 超过 10KB 的字段截断，加 `"...[truncated]"` 后缀
- 顶层 span 的 `parent_id` 为 `null`

### 5.4 功能 F3：教学注释生成

**输入**：span dict

**输出**：注释字符串（中文，≤100 字）

**生成规则**：

| type | 模板 |
|------|------|
| `agent_run` | `f"这是 Agent 的一次完整执行。目标：{extract_question(input)}"` |
| `node` | `f"Agent 进入 {name} 节点。{node_role_hint(name)}"` |
| `llm_call` | `f"Agent 调用 {model_name} 决定下一步。{extract_decision(output)}"` |
| `tool_call` | `f"Agent 调用 {tool_name} 工具，参数：{summarize(input)}。返回：{summarize(output)}"` |
| error | `f"⚠️ 出错：{error}。{common_cause_hint(error)}"` |

**辅助函数职责**：
- `extract_question(input)`：从 input 提取用户问题（最多 30 字）
- `node_role_hint(name)`：根据节点名给提示（如 "reason" → "这一步 Agent 在推理"）
- `extract_decision(output)`：从 LLM output 提取决策（如 "选择了调用 search 工具"）
- `summarize(text)`：截断到 50 字 + "..."
- `common_cause_hint(error)`：根据错误类型给排查建议

### 5.5 功能 F4：3 行代码接入 API

**用户使用方式（推荐：wrap）**：
```python
import agenteval
agenteval.init()

graph = build_my_langgraph()  # 用户的 LangGraph
traced_graph = agenteval.wrap(graph)  # 1 行包装
result = traced_graph.invoke({"messages": [("user", "LangGraph 是什么？")]})
# 自动采集并打印 trace
```

**可选方式（装饰器，要求函数接受 **kwargs）**：
```python
import agenteval
agenteval.init()

@agenteval.trace
def run_agent(question, **kwargs):
    return graph.invoke({"messages": [("user", question)]}, config=kwargs)

run_agent("LangGraph 是什么？")
```

**`init()` 行为**：
- 创建 `AgentEvalCallbackHandler` 实例，存到模块级变量 `_handler`
- 记录 `db_path`（Week 1 不使用）
- 幂等：重复调用不报错，覆盖旧 handler

**`wrap(graph)` 行为**：
- 返回一个新的 Runnable，内部对 `graph.invoke()` 自动传入 `config={"callbacks": [_handler]}`
- 用户传入的 `config` 与注入的 callbacks **合并**，不覆盖（保留 `thread_id` 等）
- 调用前 `handler.reset()`
- 执行结束后，调用 `serializer.build_trace(_handler)` 获取 trace
- `verbose=True` 时打印 trace JSON 到控制台；trace 始终可通过 `agenteval.last_trace()` 获取
- 若 invoke 抛异常，仍调用 `build_trace` 记录 error span，然后向上抛异常
- `ainvoke` / `stream` / `astream` 抛 `NotImplementedError`（Week 1 只支持同步 invoke）

**`@trace` 装饰器行为**：
- 仅用于函数签名包含 `**kwargs` 的函数
- 调用前 `handler.reset()`
- 把 `callbacks=[_handler]` 通过 kwargs 传给原函数（原函数需自行传给 graph.invoke 的 config）
- 其余行为与 `wrap()` 一致

### 5.6 功能 F5：端到端示例

**文件**：`examples/react_agent_trace.py`

**内容要求**：
- 用 LangGraph 构建 ReAct Agent
- 至少 2 个 tool（如 search + calculator，可用 mock）
- 用 `agenteval.init()` + `agenteval.wrap()` 接入
- 运行 3 个测试用例：
  1. 正常调用（LLM → tool → LLM → 输出）
  2. tool 抛异常（error span 验证）
  3. 多轮对话（验证 trace 独立性）
- 每个 case 打印 trace JSON

---

## 6. 开发注意事项

### 6.1 LangGraph callback 关键陷阱

1. **`run_id` 是 UUID 对象，不是字符串**
   - 存入 dict 时要 `str(run_id)`，否则查找失败
   - `parent_run_id` 同理

2. **`serialized` 字段结构不固定**
   - 不同事件类型的 `serialized` 内容不同
   - `name` 字段可能不存在，要用 `serialized.get("name", "unknown")`
   - LLM 的 `serialized` 里有模型信息，但位置不固定，需实际打印确认

3. **callback 内部异常会中断 Agent**
   - 所有 `on_*` 方法内部必须 try-except
   - 异常时记录日志，不向上抛

4. **`on_chain_end` 的 `outputs` 可能是 LangGraph state 对象**
   - 不能直接 `json.dumps`
   - 需要转成 dict：`dict(outputs)` 或手动提取关键字段

5. **流式输出（stream）的 callback 行为不同**
   - Week 1 不支持 stream，文档中说明限制
   - `ainvoke`（async）也不支持，Week 1 只支持同步 `invoke`

### 6.2 trace 树构建陷阱

1. **不是所有 `on_chain_end` 都有对应 `on_chain_start`**
   - 某些内部 chain 可能只触发 end
   - serializer 要处理"只有 end 没有 start"的情况

2. **`parent_run_id` 可能为 None**
   - 顶层 run 的 `parent_run_id` 是 None
   - 第一个 `parent_run_id is None` 的 run 是 root

3. **children 顺序**
   - `self._children[parent_id]` 应按 `started_at` 排序
   - 不保证 callback 触发顺序就是执行顺序

4. **循环引用**
   - LangGraph state 里可能有不可序列化的对象
   - 序列化前用 `json.dumps(trace, default=str)` 兜底

### 6.3 数据截断规则

| 字段 | 截断阈值 | 处理 |
|------|---------|------|
| `input` / `output` | 10KB | 截断 + `"...[truncated]"` |
| `annotation` | 100 字 | 不截断（生成时控制） |
| `messages` 数组 | 20 条 | 保留前 10 + 后 10，中间用 `"...[N messages omitted]"` |
| `error` stack trace | 2KB | 截断 |

### 6.4 时间戳格式

- 统一用 ISO 8601：`datetime.now(timezone.utc).isoformat()`
- 不要用本地时间
- 不要用 time.time()（浮点秒）

### 6.5 日志规范

- 用 `logging` 模块，不用 `print`（print 只用于最终 trace 输出）
- logger 名字：`agenteval.collector`、`agenteval.serializer` 等
- 默认级别 WARNING，verbose=True 时 DEBUG

---

## 7. 技术约束

### 7.1 版本约束

| 依赖 | 版本 | 原因 |
|------|------|------|
| Python | >=3.11 | 与 pyproject 一致；3.10 于 2026-10 停止维护 |
| langgraph | >=1.0 | 实测 1.2.10；回调行为详见 docs/CALLBACK_EVENTS.md |
| langchain-core | >=1.0 | 实测 1.5.3；BaseCallbackHandler 所在 |
| langchain-openai | >=1.0 | 实测 1.4.2；示例用 |

### 7.2 依赖最小化

Week 1 的 `pyproject.toml` 只声明以下运行时依赖：
- `langchain-core`（BaseCallbackHandler）
- 不需要 `langgraph` 作为依赖（用户自己装），但示例需要

**禁止引入**：
- `langchain`（完整包，太重）
- `langsmith`（竞品）
- `streamlit`（Week 2 才用）
- `sqlite3`（Python 内置，无需声明）

### 7.3 兼容性约束

- 只支持同步 `invoke`，不支持 `ainvoke` / `stream`
- 只支持 LangGraph，不支持 LangChain 原生 chain
- 只支持单次 invoke，不支持并发（多次 invoke 要串行）

### 7.4 代码风格

- 用 `type hints`（Python 3.11+ 语法，如 `str | None`）
- 用 `dataclass` 或 `TypedDict` 定义数据结构
- 函数文档用 docstring（Google 风格）
- 文件编码 UTF-8

### 7.5 测试约束

- 每个模块至少 3 个测试用例：正常、边界、异常
- 测试不依赖真实 LLM API，用 mock callback 事件
- 测试覆盖率目标：核心逻辑 ≥80%

---

## 8. 后续扩展方向

### 8.1 Week 2：存储层 + Web 列表

**新增模块**：
- `storage/db.py`：SQLite CRUD
- `storage/schema.py`：traces 表 + 常量定义
- `web/app.py`：Streamlit 主入口
- `web/list_view.py`：trace 列表页

**接口变化**：
- `__init__.py` 的 `init()` 真正创建数据库
- `wrap()` 包装对象把 trace 写入 SQLite，而非仅打印
- `init()` 新增可选参数 `experiment_id: str | None`，标记当前实验组（为 V2 方案对比预留）

**数据表结构**：
```
traces 表：
    id TEXT PRIMARY KEY
    created_at TIMESTAMP
    status INTEGER          -- 0=success, 1=error, 2=running
    framework TEXT
    agent_name TEXT
    trace_json JSON         -- SQLite 3.9+ JSON1，支持 json_extract() 路径查询
    experiment_id TEXT      -- 方案对比预留：同 experiment_id 的多次 trace 是同一实验不同方案
```

**status 常量映射**（在 `storage/schema.py` 定义）：
```python
STATUS_SUCCESS = 0
STATUS_ERROR = 1
STATUS_RUNNING = 2

STATUS_LABELS = {0: "success", 1: "error", 2: "running"}
```

**索引**：
```sql
CREATE INDEX idx_traces_created ON traces(created_at DESC);
CREATE INDEX idx_traces_status ON traces(status);
CREATE INDEX idx_traces_experiment ON traces(experiment_id);
```

**Week 2 补充任务（基于专家反馈）**：
- `on_llm_end` 补充采集 `model_version`（从 `response.llm_output` 或 `invocation_params` 提取），存入 span metadata，确保同模型名不同版本的 trace 可区分
- 列表页展示每条 trace 的总 token 数（从 trace_json 聚合）和总耗时（root_span 的 started_at → ended_at）
- `experiment_id` 在 MVP 阶段不暴露 UI，但 `init(experiment_id="xxx")` 传入时写入数据库，为 V2 方案对比面板预留数据

### 8.2 Week 3：树状图可视化

**新增模块**：
- `web/trace_view.py`：树状图渲染

**技术选型**：
- 用内置 `st.graphviz_chart`（零依赖）或 `plotly` 渲染树（不用维护差的 `streamlit-mermaid`）
- 展示 span 节点 + annotation + input/output 折叠

### 8.3 Week 4：安全 replay

**新增模块**：
- `replay/runner.py`：replay 执行引擎
- `replay/policy.py`：span 类型判断
- `web/replay_view.py`：replay 面板

**核心逻辑**：
```
replay(trace_id, span_id, new_input):
    span = load_span(trace_id, span_id)
    if span.type == "llm_call":
        return llm.invoke(new_input)  # 真实重跑
    elif span.type == "tool_call":
        return span.output  # 返回录播响应
    else:
        raise NotReplayableError
```

### 8.4 V2：诊断 Agent

**新增模块**：
- `agent/diagnostic.py`：无状态诊断 Agent

**Tools**：
- `get_trace(trace_id)`
- `get_span(trace_id, span_id)`
- `compare_traces(trace_id_1, trace_id_2)`

**约束**：
- 用 LangGraph 实现（吃自己狗粮）
- 无 Memory（单次分析）
- 输出自然语言诊断报告

### 8.5 扩展方向（不在 MVP）

| 方向 | 说明 |
|------|------|
| 多框架支持 | OpenAI Agents SDK、CrewAI 的 callback 适配 |
| trace diff | 对比两次执行，高亮差异 |
| 导出 OTLP | 兼容 OpenTelemetry 生态 |
| 性能分析 | span 耗时统计、token 成本归因 |

### 8.6 V3-P1：OpenAI Agents SDK 采集适配

**采集层解耦**：
- `collector/core.py` — 框架无关 `SpanCollector`（start/end/error 状态机），
  LangGraph callback 与 SDK 适配器共用；`collector.framework` 决定
  trace.framework（langgraph / openai_agents）。
- `collector/callback.py` — 重构为 `SpanCollector` 薄适配层，内部属性
  （`_states` / `_children` / `_root_run_id` / `agent_name`）通过属性转发保持兼容。
- `collector/agents_sdk_adapter.py` — `AgentEvalTracingProcessor(TracingProcessor)`。

**关键接口契约**（openai-agents 0.21 实测）：
- `agents.tracing.set_trace_processors(list)` **替换**现有处理器（含默认上传
  OpenAI 平台的导出器）；回调全部为同步方法。
- Span 属性：`trace_id` / `span_id` / `parent_id` / `span_data` / `error` /
  `started_at` / `ended_at`（ISO 字符串）。
- span_data.type：`agent` / `function` / `generation` / `custom` 等；
  generation 有 `model` / `model_config` / `usage`（input_tokens/output_tokens/
  total_tokens），function 有 `name` / `input` / `output` / `mcp_data`。

**映射规则**：
| SDK span type | 我们的 span type | 说明 |
|---------------|------------------|------|
| agent | agent_run（根）/ node（嵌套） | handoff 子代理按 node |
| function | tool_call | 绝不真实执行（replay 录播） |
| generation | llm_call | model/usage 归入 metadata |
| custom/guardrail/handoff/response 等 | node | 其余兜底 |

**接入方式**：`agenteval.init(agents_sdk=True)`（需 `pip install
"agenteval-debugger[agents-sdk]"`）。trace 结束按 trace_id 隔离并发执行；
根 span 用首个 llm 输入/末个 llm 输出补齐，保证 Web 对话预览可用。

**实测要点**（openai-agents 0.21 + DeepSeek）：
- Runner.run 实际 span 结构为 task → agent → turn → response；适配器跳过
  task/turn 包装，把首个 agent 提升为根，response 映射为 llm_call。
- response span 的 model / usage / output 在 **span 结束时**才填充，须在
  on_span_end 补捕获（改名 + 合并 metadata）。
- response span 不带 input（Response.prompt=None），SDK trace 的根 input 为空，
  Web 对话预览显示 "—"（已知限制，等 SDK 补 input 或包装 Runner.run）。

---

## 附录：验收清单（Week 1 结束时检查）

### 功能验收
- [ ] `import agenteval` 不报错
- [ ] `agenteval.init()` 可重复调用
- [ ] `agenteval.wrap(graph)` 可用，且用户自带 config 不被丢弃
- [ ] `@agenteval.trace` 装饰器可用
- [ ] ReAct Agent 运行后输出 trace JSON
- [ ] trace JSON 是正确嵌套树形结构
- [ ] 每个 span 有 `annotation` 字段
- [ ] error span 被正确记录
- [ ] tool span 的 input/output 被采集
- [ ] LLM span 的 token usage 被采集

### 示例验收
- [ ] `examples/react_agent_trace.py` 可运行
- [ ] 包含正常调用、tool 异常、多轮 3 个 case
- [ ] 每个 case 输出 trace JSON

### 测试验收
- [ ] `tests/test_callback.py` 通过
- [ ] `tests/test_serializer.py` 通过
- [ ] `tests/test_annotator.py` 通过
- [ ] 不依赖真实 LLM API

### 文档验收
- [ ] README 有 quickstart
- [ ] 新用户 10 分钟能跑通示例

---

*本文档供 Codex / Claude Code 直接执行。如遇 LangGraph API 与文档描述不符，以实际行为为准并记录到注意事项。*
