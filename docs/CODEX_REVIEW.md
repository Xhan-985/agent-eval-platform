# Codex 对 AgentEval 架构的独立审查报告

> 审查时间：2026-08-09
> 审查者：Codex（OpenAI coding agent）
> 审查对象：docs/HANDOVER.md（开发交接文档）
> 状态：已采纳关键建议并修订文档

---

## 1. 对项目目标的理解

AgentEval 是一个面向 Agent 学习者/初学者的执行调试器，不是企业级可观测平台。核心价值是解决"初学者看不懂 Agent 中间过程"的问题，三个差异化卖点：

- **3 行代码接入**：`import agenteval` + `init()` + 装饰器，比 Langfuse/Phoenix 门槛低
- **教学化注释**：每个 span 用中文解释"这一步在干什么、为什么"，这是现有工具都不做的
- **安全 replay**：LLM 节点可改输入重跑，tool 节点只回放录播响应，避免副作用（发邮件、写库等）

技术形态是单机、零配置（pip install 即用）的 SDK + SQLite + Streamlit 单体工具，MVP 只支持 LangGraph 同步 invoke。非目标很清晰：不做企业监控、不做评估打分、不做多框架支持。MVP 本身不是 Agent 系统，V2 才加无状态诊断 Agent（用 LangGraph 吃自己的狗粮）——这个克制是对的。

一句话概括："让学习者能看懂 Agent 为什么这么调" 的调试器，先确定性工程、后 LLM 增强。

## 2. 当前设计是否符合 2026 年 Agent 工程实践

**方向正确，细节有部分过时。** 可观测性仍然是 Agent 工程的核心支柱，面向学习者的差异化定位依然成立；但文档锁定的技术版本和个别选型停留在 2024-2025 年初的认知上。

### 符合实践的部分
- callback 采集仍是 LangGraph 生态的合法接入点，`BaseCallbackHandler` + `run_id`/`parent_run_id` 构建树的方法没有过时
- 单体优先、零配置、诚实降级（tool 不能 replay 就明说）是好的工程取舍
- 先做确定性工具、V2 再上诊断 Agent，避免为 AI 而 AI
- SQLite 单库 + JSON 嵌套存树形 trace，对 MVP 规模完全合理

### 偏离 2026 实践的部分
- 版本约束停留在 `langgraph>=0.2` / `langchain-core>=0.3`（2024 年的版本号），2026 年实际早已迭代到 0.4+ 的新运行时，开工时必须重新验证 API 行为
- 完全没有利用 LangGraph 内建的 checkpoint/time-travel（时间旅行）机制，自研 replay 与官方能力重叠
- 数据格式是私有 JSON，与 OpenTelemetry GenAI 语义约定（`gen_ai.*`，2025 年起成为事实标准）不对齐，后续想导出 OTLP 兼容 Langfuse/Phoenix 需要重写序列化层
- `streamlit-mermaid` 组件维护状态差，有更好的替代

## 3. 技术方案中过时或需要优化的地方

### 必须处理（会直接阻塞 Week 1 验收）

| # | 问题 | 说明与建议 |
|---|------|-----------|
| 1 | pyproject.toml 缺失 | REPO_INIT/HANDOVER 都声明初始 commit 应含它，实际仓库没有。没有它 `pip install -e .`、pytest、ruff 配置全都无从谈起。Week 1 第一件事就是补上 |
| 2 | 装饰器 API 契约有缺陷 | HANDOVER 写 `@trace` 包装用户函数并在内部强传 `config={"callbacks": [...]}`，但示例用户函数签名是 `def run_agent(question)`，传 config 会直接 TypeError。建议改为 `agenteval.wrap(graph)` 返回注入好 callback 的包装图（示例仍是 3 行），装饰器保留但要求被包装函数接受 config 参数 |
| 3 | 版本约束过旧，需实测 | 文档锁 `langgraph>=0.2`。0.4+ 换了响应式运行时，callback 事件参数（尤其 LLM 的 messages、serialized 结构）大概率变了。Week 1 必须先做"事件清单调研"再写 handler，不能照文档直接写 |
| 4 | 本机环境与文档不符 | 本机 Python 3.14.6，`.python-version` 写 3.10（2026-10 就到安全维护末期）。建议 `requires-python >=3.11` 或 `>=3.12`，并先在本机验证 3.14 兼容性。另外沙箱网络受限，安装依赖时需要你批准联网 |

### 建议优化（不影响开工，但影响质量）

| # | 问题 | 说明与建议 |
|---|------|-----------|
| 5 | replay 与 LangGraph 原生能力重叠 | LangGraph 自带 checkpoint + 时间旅行：可回放到任意 checkpoint、`update_state` 修改输入后 fork 重跑。文档完全没提。MVP 可仍按"录播 + LLM 重跑"实现（更简单可控），但 Week 1 调研阶段应顺带验证 checkpoint 机制，Week 4 决策时二选一 |
| 6 | trace schema 应对齐 OTel GenAI 语义 | 现在 span 字段（type/name/input/output）是私有约定。建议内部统一为 `llm_call` / `tool_call` / `node` / `agent_run`（文档已基本如此），字段命名对齐 `gen_ai.agent.*`，未来加 OTLP exporter 就不用重写 |
| 7 | 树状图组件选型过时 | `streamlit-mermaid` 依赖外部 CDN、和新版 Streamlit 兼容性差。建议用内置 `st.graphviz_chart`（零依赖渲染树）或 `st.html` 内嵌 mermaid.js；交互细节用 `st.expander` 折叠 input/output |
| 8 | 只支持同步 invoke | 2026 年 async/stream 已是主流。MVP 明确不做是对的，但 API 层要留口子（后续用 `astream_events` 补），README 写清限制 |
| 9 | LLM replay 的可行性依赖采集信息 | 从 callback 记录重跑 LLM 节点，需要采集模型名、完整 messages、参数（temperature 等），仅靠 prompts 字符串不够。采集阶段就要把 `invocation_params`/messages 存进 span metadata |
| 10 | 存储层 span 级检索弱 | 整个 trace 塞一个 TEXT 字段，列表页没问题，但"按类型筛 span"会很难。MVP 可接受，建议 Week 2 建表时顺带加一个 spans 表或 JSON1 索引，成本很低 |

### 可选加分（不阻塞，列入路线图）

- **MCP 输出**：2026 年 MCP 已普及，V2 可暴露本地 MCP server，让 AI IDE 直接查 trace（比 Web 界面更符合"学习者在编辑器里调试"的场景）
- **LLM 增强注释开关**：模板注释确定性好、零成本，保留为主；可加可选"LLM 深度注释"模式，与 V2 诊断 Agent 复用
- **trace diff / 导出 Langfuse 格式**：文档 V2 路线已列，方向对

## 4. 预计实现路线

原 5 周框架总体合理，建议保持，仅做两处微调（Week 1 先补基建；Week 4 前先做 checkpoint 技术验证）：

| 阶段 | 目标 | 关键产出 | 微调 |
|------|------|---------|------|
| Week 1 | 采集 SDK + 教学注释 | 3 行接入、带注释 trace JSON、单测 | 先补 pyproject/版本锁定/事件调研 |
| Week 2 | 存储 + 列表页 | SQLite 入库、Streamlit 列表 + 筛选 | 建表时加 spans 索引 |
| Week 3 | 树状图可视化 | 树 + 注释 + input/output 折叠 + 错误高亮 | 用 graphviz/mermaid 替代 streamlit-mermaid |
| Week 4 | 安全 replay | LLM 重跑 + tool 录播 + 对比面板 | 先验证 LangGraph checkpoint，再定 replay 底层 |
| Week 5 | 打磨 + 发布 | PyPI 可装、README 10 分钟跑通、社区材料 | 补 async/stream 限制说明 |

砍量预案（沿用文档）：Week 1/3 不达标砍 replay，保证"采集 + 可视化"这个核心闭环；Week 1 内优先级从高到低：callback handler → trace 树 → 注释 → API → 示例/测试。

## 5. Week 1 开发任务拆解

总工时约 30 小时（每天 3-5 小时），比文档多了"补基建"和"事件调研"两块前置工作，建议 6 天而不是 5 天，Day 1-2 是关键：

| # | 任务 | 产出 | 预计 | 验收要点 |
|---|------|------|------|---------|
| 0 | 仓库基建补齐 | pyproject.toml（依赖/requires-python/pytest/ruff 配置）、CI 可选 | 2h | `pip install -e .` 可装 |
| 1 | 环境验证 + 事件调研（依赖联网） | 跑通官方 ReAct 示例；一份"callback 事件清单"：事件名、触发时机、关键参数、serialized 实际结构 | 5h | 确认 on_llm_start 的 messages/params 在哪、0.4+ 行为差异；记录到 docs |
| 2 | 数据结构定义 | SpanState/Trace JSON schema（含 metadata 存模型参数、截断规则） | 2h | 字段对齐 OTel 语义，可 JSON 序列化 |
| 3 | callback handler | collector/callback.py，7 个 on_* 方法，内部 try-except 兜底 | 5h | run_id 字符串化、父子关系、token usage 采集 |
| 4 | trace 树构建 | collector/serializer.py：递归建树、10KB 截断、default=str 兜底 | 4h | 嵌套结构正确、可 json.loads |
| 5 | 教学注释 | collector/annotator.py：5 种 span 模板、中文 ≤100 字、纯函数 | 3h | 每种类型都有注释 |
| 6 | 对外 API | __init__.py：init() 幂等、wrap(graph) + @trace（修复签名问题）、异常也出 trace | 3h | 3 行接入可用 |
| 7 | 端到端示例 | examples/react_agent_trace.py：正常 / tool 异常 / 多轮 3 个 case | 3h | 可运行，trace 正确 |
| 8 | 单元测试 | mock callback 事件，不依赖真实 LLM API | 4h | 核心逻辑覆盖率 ≥80% |
| 9 | 边界处理 + 文档 | 大输出截断、多次 invoke 独立、README quickstart + 已知限制 | 3h | Agent 异常时 trace 仍完整 |

Week 1 验收标准（保持文档原样）：`pip install -e .` 成功 → 3 行接入 ReAct Agent → 输出带注释的嵌套 trace JSON → 3 个示例 case 全过 → 单测通过 → 新用户按 README 10 分钟跑通。

---

## 审查结论

Codex 的审查质量高，发现了设计者视角的盲点（特别是装饰器 API 签名冲突和 pyproject.toml 缺失）。建议作为项目决策记录归档，后续 Week 4 决策 replay 方案时回看第 3 节第 5 条。
