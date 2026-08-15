# AgentEval V3 开发计划（性能分析 → 多框架）

> 版本：v3.0 | 更新时间：2026-08-15 | 分支：v3（不合并 main，除非用户明确要求）
> 依据：docs/AgentEval_PROJECT_DOC.md 11.4；docs/HANDOVER.md 8.5

## 1. 路线（重审后的顺序）

| 版本 | 功能 | 规模 | 状态 |
|------|------|------|------|
| V3-P0（0.3.0） | 性能分析 + token 成本归因 | 1-2 周 | 本期 |
| V3-P1（0.4.0） | 多框架支持（仅 OpenAI Agents SDK） | 2-4 周 | 规划中 |
| V3-P2（0.5.0） | 导出 OTLP | 0.5 周 | 本期（已完成） |

调整理由：
1. 多框架（OpenAI Agents SDK）是架构级改动（async 采集），且收益未被验证，
   按"先验证工具价值"原则排后；CrewAI 明确不做（生态变动快、维护成本高）。
2. 性能分析低成本、直接服务现有学习者/老师（看懂"哪一步慢、token 花在哪"），
   且需要先有性能基线，正好作为 V3 第一个交付。

## 2. V3-P0：性能分析 + token 成本归因

### 2.1 范围

- `collector/metrics.py` 扩展归因纯函数：
  - `span_duration_ms(span)` / `span_total_tokens(span)`
  - `build_span_performance(root_span)`：展平所有 span，附耗时/耗时占比/token/token 占比/错误标记，按耗时降序
  - `estimate_cost(trace, pricing)`：按模型单价估算 token 成本（可选功能，纯函数）
- Web 详情页新增"性能"tab（`web/performance_view.py`）：span 排行表
  （名称/类型/耗时/耗时占比/Token/Token 占比/错误），最慢 span 高亮，
  可选"显示成本估算"开关（默认关）
- 仪表盘：caption 增加"最慢单次执行"（不动 KPI 布局）
- `benchmarks/benchmark_large_trace.py`：合成大 trace（100/500/1000 span）性能基准，
  记录到 `docs/PERF_BASELINE.md` 作为验收基线
- README 路线图更新（v0.3.0 性能分析）；版本号升 0.3.0

### 2.2 验收标准

- [x] 详情页"性能"tab 显示 span 耗时/token 排行与占比
- [x] 1000+ span 的 trace：列表查询、详情加载、树/瀑布渲染、诊断摘要都在可控耗时内（docs/PERF_BASELINE.md）
- [x] 成本估算纯函数有测试；未配置单价时不影响其他功能
- [x] 旧功能（列表/树/时间线/replay/诊断/对比）不受影响
- [x] 全部测试通过（190 个），ruff 全绿

## 3. V3-P1：多框架支持（OpenAI Agents SDK）— 已完成（0.4.0）

### 3.1 已定决策

- async 方案：**同步回调采集，不引入 asyncio 桥接**。依据：openai-agents 0.21 的
  TracingProcessor 回调（on_trace_start / on_span_start / on_span_end / on_trace_end）
  本身就是同步接口，由 SDK 在 async 运行循环里调用；采集端无需 asyncio.run 包装，
  也不需要把采集器整体改 async。trace 结束时同步写 SQLite（单条 INSERT）。
- 注册方式：`init(agents_sdk=True)` 调用 `agents.tracing.set_trace_processors([...])`，
  替换 SDK 默认上传 OpenAI 平台的导出器（本地优先、隐私友好，README 已注明）。
- LLM span 数据捕获时机：SDK 0.21 的 response span 在 **span 结束时**才填充
  model / usage / output，因此适配器在 on_span_end 里补捕获（改名 + 合并
  metadata），start 时只建基础 span。

### 3.2 已完成

- `collector/core.py`：框架无关的 `SpanCollector`（扁平状态机 start/end/error），
  LangGraph callback 与 SDK 适配器共用；`serializer.build_trace` 读取
  `collector.framework`（langgraph / openai_agents）。
- `collector/callback.py`：重构为 `SpanCollector` 薄适配层，LangGraph 行为不变。
- `collector/agents_sdk_adapter.py`：`AgentEvalTracingProcessor`，SDK span 类型映射
  （agent→agent_run/node、function→tool_call、generation→llm_call），generation 的
  model / model_config / usage 归一化为 metadata（model_version、invocation_params、
  token_usage），OpenAI 消息 role 转为 agenteval message type（replay 兼容）；
  trace 结束按 trace_id 隔离并发执行，根 span 用首个 llm 输入/末个 llm 输出补齐
  （Web 对话预览可用）。
- `agenteval/__init__.py`：`init(agents_sdk=True)` 注册处理器；未装 openai-agents
  时给出明确中文错误提示；pyproject 新增 `[agents-sdk]` extra。
- `examples/agents_sdk_demo.py`；`tests/test_collector.py` + `tests/test_agents_sdk.py`
  （假 span 对象，不依赖真实 API）。
- 真实端到端验证：本地用 DeepSeek（deepseek-v4-flash）跑通 Runner.run，
  trace 自动入库；树为 agent_run → llm_call，模型名/正文/token 用量正确。

### 3.3 待办

- Web 列表按 framework 过滤/展示（可选，用户确认后做）

### 3.4 验收

- [x] 同一套 Web / 诊断 / replay 对 LangGraph 与 OpenAI Agents SDK 生成的 trace 都可用

### 3.5 已知限制

- SDK 0.21 的 response span 不记录输入（Response.prompt 为 None），SDK trace
  的根 input 为空，Web 列表"对话内容"预览显示 "—"；等 SDK 补 input 或后续
  包装 Runner.run 再完善。
- `init(agents_sdk=True)` 会替换 SDK 默认导出器（trace 只写本地，不上传 OpenAI）。

## 4. 已知限制

- 性能分析只统计已采集的数据（token 需模型返回 usage 才有值）
- 成本估算依赖单价配置，默认不展示，避免误导

---

*本文档随 V3 进度持续更新。*

## 5. V3-P2：导出 OTLP — 已完成（0.5.0）

### 5.1 已定决策

- **零依赖实现**：不引入 opentelemetry SDK，直接生成 OTLP/HTTP JSON 协议的
  `ExportTraceServiceRequest`（`agenteval/export/otlp.py`），纯函数可测。
- 导出方式两种：`export_otlp_json()` 写 JSON 文件（可导入 Jaeger 等）；
  `send_otlp_http()` 用 urllib POST 到任意 OTLP/HTTP 端点（如
  `http://localhost:4318/v1/traces`）。
- id 派生：agenteval 的字符串 id（UUID / span 名）定长哈希为
  32/16 位 hex；已是合法 hex 则原样保留。
- 时间戳：ISO 8601 → unix 纳秒；proto3 JSON 约定 int64 用字符串。

### 5.2 字段映射

- resource attributes：`service.name=agenteval`、`service.version`、
  `agent.framework`、`agent.name`。
- 通用 span attributes：`span.type` / `span.name` / `annotation` / `error`。
- llm_call 附加 `gen_ai.*`：`gen_ai.system`、`gen_ai.request.model`、
  `gen_ai.usage.input_tokens`（兼容 prompt_tokens）/ `output_tokens`
  （兼容 completion_tokens）/ `total_tokens`。
- error span：`status.code=2` + exception 事件（exception.type/message）。

### 5.3 验收

- [x] `to_otlp_payload` 纯函数转换正确（结构 / id / parent / 时间戳 / 属性 / 错误状态）
- [x] `export_otlp_json` 写文件，trace 不存在返回 0
- [x] `send_otlp_http` 用 mock urlopen 验证 POST + Content-Type + body
- [x] 全部测试通过（213 个），ruff 全绿；版本 bump 0.5.0
