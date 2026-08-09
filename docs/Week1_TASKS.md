# AgentEval Week 1 任务拆解

> 目标：实现 LangGraph callback handler，能采集 trace 并生成教学注释
> 预计耗时：21-34 小时（每天 3-5 小时，一周完成）
> 前置条件：已读 AgentEval_PROJECT_DOC.md

---

## 技术背景（基于最新文档确认）

LangGraph 的 tracing 基于 LangChain 的 callback 系统：

- **核心类**：`BaseCallbackHandler`（来自 `langchain_core.callbacks`）
- **关键方法**：
  - `on_chain_start` / `on_chain_end` / `on_chain_error`：graph node 进入/退出/出错
  - `on_llm_start` / `on_llm_end`：LLM 调用
  - `on_tool_start` / `on_tool_end`：tool 调用
- **树构建机制**：每个事件带 `run_id`（UUID）和 `parent_run_id`，通过 parent 链构建树
- **接入方式**：`graph.invoke(input, config={"callbacks": [handler]})`

**关键认知**：LangGraph 中每个 node、每次 LLM 调用、每次 tool 调用都是 LangChain Runnable，callback 会自动流经整个执行树，无需逐个节点埋点。

---

## 任务依赖关系

```
任务1（环境搭建）
    ↓
任务2（研究callback）→ 任务3（实现handler）
                          ↓
                    任务4（构建trace树）→ 任务5（教学注释）
                                            ↓
                                      任务6（API封装）
                                            ↓
                                      任务7（集成测试）
                                            ↓
                                      任务8（边界处理）
```

---

## 任务 1：环境搭建与 LangGraph 跑通

**预计耗时**：2-3 小时

### 目标
本地能跑通一个 LangGraph ReAct Agent，为后续 callback 接入做准备。

### 具体步骤
1. 创建 Python 虚拟环境（Python 3.11+，仓库 `.python-version` 为 3.12）
2. 安装依赖：`langgraph`、`langchain-openai`
3. 配置 OpenAI API key（或用其他支持的模型）
4. 复制 LangGraph 官方 ReAct Agent 示例
5. 运行 Agent，确认能回答问题

### 输入
- LangGraph 官方文档（quickstart）
- OpenAI API key

### 输出
- 一个能运行的 `example_agent.py` 脚本
- 确认 Agent 能正确调用 tool 回答问题

### 验收标准
- [ ] `python example_agent.py` 能运行
- [ ] Agent 能调用至少 1 个 tool（如搜索/计算器）
- [ ] 输出正确的回答
- [ ] 控制台无报错

### 难点
- API key 配置（建议用环境变量，不硬编码）
- LangGraph 版本兼容性（建议锁定版本）

### 学习资料
- LangGraph 官方 quickstart
- 搜索 "LangGraph ReAct agent example 2026"

---

## 任务 2：研究 callback 机制

**预计耗时**：2-3 小时

### 目标
理解 BaseCallbackHandler 的接口，明确每种事件何时触发、参数含义。

### 具体步骤
1. 阅读 `langchain_core.callbacks.base.BaseCallbackHandler` 源码/文档
2. 列出所有 `on_*` 方法
3. 在任务 1 的 Agent 上加一个 print callback，观察事件触发顺序
4. 记录每个事件的参数（`serialized`、`inputs`、`outputs`、`run_id`、`parent_run_id` 等）

### 输入
- 任务 1 的 `example_agent.py`

### 输出
- 一份 callback 事件清单（文档形式）：
  - 事件名
  - 触发时机
  - 关键参数
  - 在 trace 树中的对应 span 类型

### 验收标准
- [ ] 能画出 ReAct Agent 执行时的事件流时序图
- [ ] 明确 `run_id` 和 `parent_run_id` 的关系
- [ ] 能区分 chain 事件、llm 事件、tool 事件
- [ ] 知道每个事件的 `serialized` 里有什么信息

### 难点
- 事件类型多，容易混淆
- `serialized` 字段的结构需要实际打印才能理解

### 学习资料
- `langchain_core.callbacks.base.BaseCallbackHandler` 源码
- 搜索 "LangChain BaseCallbackHandler methods reference"

### 示例事件清单格式
```
事件：on_chain_start
触发时机：graph node 开始执行
关键参数：
  - serialized: {"name": "reason", ...}（节点名）
  - inputs: {...}（输入 state）
  - run_id: UUID
  - parent_run_id: UUID 或 None（顶层为 None）
对应 span 类型：agent_step
```

---

## 任务 3：实现基础 callback handler

**预计耗时**：4-6 小时

### 目标
实现 `AgentEvalCallbackHandler` 类，采集所有事件并暂存。

### 具体步骤
1. 创建 `agenteval/collector/callback.py`
2. 实现 `AgentEvalCallbackHandler(BaseCallbackHandler)`
3. 维护 `self._states: dict[UUID, SpanState]` 保存每个 run 的上下文
4. 实现以下方法：
   - `on_chain_start`：记录 span 开始 + input
   - `on_chain_end`：记录 span 结束 + output
   - `on_chain_error`：记录错误
   - `on_llm_start`：记录 LLM 调用开始
   - `on_llm_end`：记录 LLM 调用结束 + token usage
   - `on_tool_start`：记录 tool 调用开始
   - `on_tool_end`：记录 tool 调用结束
5. 暂时用 print 验证采集正确

### 输入
- 任务 2 的事件清单

### 输出
- `agenteval/collector/callback.py`
- 能在 Agent 运行时打印所有事件

### 验收标准
- [ ] 所有 7 个 callback 方法都已实现
- [ ] 运行 Agent，能看到每个事件的 print
- [ ] `run_id` 和 `parent_run_id` 正确记录
- [ ] LLM 调用的 token usage 被采集
- [ ] tool 调用的 input/output 被采集
- [ ] 错误事件被捕获，不会中断 Agent 执行

### 难点
- **run_id 维护**：需要用 dict 缓存每个 run 的状态，start 时存入，end 时取出
- **parent_run_id 判空**：顶层 run 的 parent_run_id 为 None，要正确处理
- **serialized 解析**：不同事件类型的 serialized 结构不同，需要实际打印确认

### 设计要点
- `SpanState` 应包含：`started_at`、`input`、`name`、`type`
- 不要在此任务中构建树，只采集扁平事件
- 错误处理：callback 内部异常不能影响 Agent 执行，要 try-except

---

## 任务 4：构建 trace 树形结构

**预计耗时**：4-6 小时

### 目标
把扁平的事件流组装成嵌套的 trace JSON 树。

### 具体步骤
1. 创建 `agenteval/collector/serializer.py`
2. 定义 trace JSON 数据结构（参考项目文档第 8.4 节）
3. 利用 `parent_run_id` 构建父子关系：
   - 维护 `run_id → children` 映射
   - 顶层 run（parent_run_id 为 None）作为 root
4. 在 `on_chain_end` 时组装 span（此时 input/output 都已采集）
5. Agent 执行结束后，序列化完整 trace JSON
6. 输出到文件或控制台验证

### 输入
- 任务 3 的 callback handler

### 输出
- `agenteval/collector/serializer.py`
- 能输出正确的嵌套 trace JSON

### 验收标准
- [ ] 输出的 JSON 是正确的嵌套树形结构
- [ ] root span 的 `parent_run_id` 为 null
- [ ] 子 span 正确挂在父 span 的 `children` 数组下
- [ ] 每个 span 有 `span_id`、`type`、`name`、`input`、`output`、`started_at`、`ended_at`
- [ ] JSON 能通过 `json.loads` 解析
- [ ] 树的深度和 Agent 执行结构一致（如 ReAct Agent 有 LLM→tool→LLM 的循环）

### 难点
- **树构建时机**：不能在每个事件实时构建，要在 `on_chain_end` 时组装（此时该 span 完整）
- **顶层识别**：如何判断哪个 run 是 trace root（parent_run_id 为 None）
- **循环引用**：state 里可能有 LangGraph 的内部对象，序列化时要转成 dict

### 设计要点
- span 类型映射：
  - `on_chain_*` → `agent_step`（如果是顶层）或 `node`（如果是子节点）
  - `on_llm_*` → `llm_call`
  - `on_tool_*` → `tool_call`
- 序列化前要把 LangGraph 的 state 对象转成纯 dict（用 `dict()` 或手动转换）
- 大对象截断（如完整 messages 历史），避免 JSON 过大

### 验证方法
把 trace JSON 保存到文件，用 `jq` 或 JSON viewer 检查树结构是否正确。

---

## 任务 5：实现教学注释生成器

**预计耗时**：3-4 小时

### 目标
为每种 span 自动生成"在干什么、为什么"的教学注释。

### 具体步骤
1. 创建 `agenteval/collector/annotator.py`
2. 为每种 span 类型编写注释生成逻辑：
   - `agent_step`（顶层）：说明这是 Agent 的一次完整执行
   - `node`：说明这个节点在 Agent 流程中的作用
   - `llm_call`：说明 Agent 在调用 LLM 做决策
   - `tool_call`：说明 Agent 在调用工具获取信息
   - `error`：说明出错原因 + 常见排查方向
3. 在 serializer 组装 span 时调用 annotator 生成注释
4. 注释要简洁（1-2 句话），面向初学者

### 输入
- 任务 4 的 trace JSON

### 输出
- `agenteval/collector/annotator.py`
- 每个 span 的 `annotation` 字段有内容

### 验收标准
- [ ] 每种 span 类型都有注释
- [ ] 注释是中文（或英文，看你目标用户）
- [ ] 注释解释了"这一步在干什么"
- [ ] 注释不超过 2 句话
- [ ] LLM span 注释提到模型名和决策结果（如"选择了调用 search 工具"）
- [ ] tool span 注释提到工具名和返回摘要
- [ ] error span 注释给出可能原因

### 注释示例
```
llm_call span:
"Agent 正在调用 gpt-4o-mini 决定下一步。
基于用户问题和历史对话，选择了调用 search_web 工具。"

tool_call span:
"Agent 调用了 search_web 工具搜索 'LangGraph 教程'。
返回了 3 条结果，包含标题和摘要。"

error span:
"⚠️ 这一步出错了：TimeoutError。
可能原因：API 调用超时，建议检查网络或增加重试。"
```

### 难点
- **决策结果提取**：LLM 的 output 里提取"选择了哪个 tool"需要解析结构化输出
- **简洁性**：注释要短但要有信息量，不能太长

### 设计要点
- 注释生成是纯函数（input span → output string），无副作用
- 不同 span 类型用不同的生成函数
- 可以加 emoji 提升可读性（⚠️ 表示错误，🔍 表示搜索等）

---

## 任务 6：对外 API 封装

**预计耗时**：2-3 小时

### 目标
实现 3 行代码接入的对外 API。

### 具体步骤
1. 创建 `agenteval/__init__.py`
2. 暴露三个 API：
   - `agenteval.init(db_path="agenteval.db")`：初始化（Week 1 只记录 db_path，不建库）
   - `agenteval.wrap(graph)`：**推荐 API**，包装 graph 并注入 callback
   - `@agenteval.trace`：可选装饰器，仅适用于签名包含 `**kwargs` 的函数
3. 内部机制：
   - `init()` 创建 callback handler 实例
   - `wrap()` 自动把 handler 加到 `config={"callbacks": [handler]}`，并与用户 config 合并
4. 暂时只打印 trace JSON，不存数据库（数据库是 Week 2）

### 输入
- 任务 3-5 的模块

### 输出
- `agenteval/__init__.py`
- 对外 API

### 验收标准
- [ ] `import agenteval` 能导入
- [ ] `agenteval.init()` 不报错
- [ ] `agenteval.wrap(graph)` 能包装 graph，invoke 后自动采集
- [ ] 用户自带 config（如 thread_id）与注入的 callbacks 正确合并
- [ ] `@agenteval.trace` 装饰器能用于接受 `**kwargs` 的函数
- [ ] 运行 Agent 后自动采集 trace 并打印
- [ ] 接入代码不超过 3 行（import + init + wrap）

### 期望的使用方式
```python
import agenteval
agenteval.init()

graph = build_my_langgraph()          # 用户的 LangGraph
traced_graph = agenteval.wrap(graph)  # 1 行包装

result = traced_graph.invoke({"messages": [("user", "LangGraph 是什么？")]})
# 自动打印带注释的 trace JSON
```

### 难点
- **wrap 设计**：用户 config 与注入 callbacks 的合并；`ainvoke`/`stream` 明确抛 `NotImplementedError`
- **callback 注入**：如何把 handler 自动加到 config 里，而不让用户手动写

### 设计要点
- MVP 只支持 `invoke`，不支持 async（简化）
- `init()` 可以接受参数（如 `db_path`、`verbose`），但都有默认值
- `init()` 必须先于 `wrap()` 调用，wrap 时绑定当前 handler
- wrap/装饰器内部捕获异常，不让采集失败影响 Agent 执行

---

## 任务 7：集成测试 + 示例

**预计耗时**：2-3 小时

### 目标
端到端跑通，写一个完整示例。

### 具体步骤
1. 创建 `examples/` 目录
2. 写一个完整示例：`examples/react_agent_trace.py`
   - 用 LangGraph 构建 ReAct Agent（带 2 个 tool：搜索 + 计算器）
   - 用 agenteval 接入
   - 运行后保存 trace JSON 到文件
3. 运行示例，检查 trace JSON 正确性
4. 写 README 的 quickstart 部分

### 输入
- 任务 1-6 的所有模块

### 输出
- `examples/react_agent_trace.py`
- README 的 quickstart 章节

### 验收标准
- [ ] 示例能端到端运行
- [ ] trace JSON 保存到文件，结构正确
- [ ] 每个 span 有教学注释
- [ ] README 的 quickstart 让新用户 10 分钟能跑通
- [ ] 示例至少包含：1 次 LLM 调用 + 1 次 tool 调用 + 1 次 error 情况

### 难点
- **示例要简单但有代表性**：不能太复杂（跑不通），也不能太简单（体现不了价值）
- **error 场景构造**：需要人为制造一个错误（如 tool 抛异常）

---

## 任务 8：边界处理 + 打磨

**预计耗时**：2-3 小时

### 目标
处理边界情况，确保各种场景不崩。

### 具体步骤
1. 测试以下边界情况：
   - Agent 抛异常：trace 是否完整记录到 error span
   - tool 返回超大结果：JSON 是否过大
   - LLM 流式输出：callback 是否正常触发
   - 多次 invoke：每次是否独立 trace
   - 空 input：是否正常处理
2. 修复发现的问题
3. 添加日志（用 logging 模块，不用 print）
4. 代码清理、注释完善

### 输入
- 任务 7 的示例

### 输出
- 修复后的代码
- 已知限制清单（写进 README）

### 验收标准
- [ ] Agent 异常时 trace 仍能保存（包含 error span）
- [ ] tool 返回大结果时自动截断（如超过 10KB 截断）
- [ ] 多次 invoke 生成多个独立 trace
- [ ] 已知限制在 README 中说明

### 难点
- **异常不丢数据**：callback 内部的异常不能影响 Agent，但 Agent 的异常要被记录
- **截断策略**：截断哪里、保留什么，要平衡可读性和信息量

---

## Week 1 整体验收

### 必须达到
- [ ] `pip install -e .` 能本地安装 agenteval
- [ ] 3 行代码接入 LangGraph Agent
- [ ] 运行后输出带教学注释的 trace JSON
- [ ] trace JSON 是正确的嵌套树形结构
- [ ] 至少 1 个完整示例可运行
- [ ] README quickstart 可让新用户跑通

### 加分项（时间允许）
- [ ] trace JSON 能保存到文件
- [ ] 错误 span 有专门的高亮标注
- [ ] 支持 stream 模式

### 未达标应对
如果 Week 1 未完成核心功能：
- **砍任务 8（边界处理）**，保证任务 1-7 完成
- **砍任务 6 的装饰器**，改为手动传 callback（用户多写 1 行代码）
- **绝对不能砍**：任务 3（callback handler）和任务 4（trace 树），这是项目根基

---

## 学习资源汇总

| 主题 | 资源 |
|------|------|
| LangGraph quickstart | LangGraph 官方文档 |
| BaseCallbackHandler | `langchain_core.callbacks.base` 源码 |
| callback 事件参考 | LangChain Callbacks reference (Python) |
| trace 树构建 | 参考 Lookspan/Langfuse 的 callback 实现思路 |
| Python 装饰器 | Python 官方教程 decorator 章节 |
| SQLite Python API | Python `sqlite3` 标准库文档（Week 2 用） |

---

## 每日建议节奏

| 天 | 任务 | 预计耗时 |
|----|------|---------|
| Day 1 | 任务 1 + 任务 2 | 4-6 小时 |
| Day 2 | 任务 3（基础 handler） | 4-6 小时 |
| Day 3 | 任务 4（trace 树） | 4-6 小时 |
| Day 4 | 任务 5 + 任务 6 | 5-7 小时 |
| Day 5 | 任务 7 + 任务 8 | 4-6 小时 |

**Day 2 和 Day 3 是关键**，如果这两天卡住，整个 Week 1 会延期。遇到问题及时查文档或求助。

---

*完成任务后，进入 Week 2：存储层 + Web 列表页。*
