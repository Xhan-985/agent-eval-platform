# AgentEval V2 开发计划（诊断 Agent / AI 助教）

> 版本：v2.0 | 更新时间：2026-08-15 | 分支：v2
> 依据：docs/AgentEval_PROJECT_DOC.md 6.3-6.5、11.4；docs/HANDOVER.md 8.4

## 1. 目标

V2 把 AgentEval 从"可观测工具"升级为"智能助教"：对任意一条（或两条）trace 运行
**无状态诊断 Agent**，输出自然语言诊断报告——哪一步可能出错、为什么、怎么改。

同时满足三个附加目标：

1. **吃自己的狗粮**：诊断 Agent 本身用 LangGraph 实现，且诊断流程由
   `agenteval.wrap()` 采集入库，每次诊断都生成一条 trace。
2. **上下文可控**：大 trace（100+ span）不直接塞给 LLM，`get_trace` 只给摘要，
   细节按需用 `get_span` 取。
3. **不破坏既有功能**：Week 1-5 的采集/存储/可视化/replay 全部保持稳定。

## 2. 总体路线（重审后的顺序）

| 优先级 | 功能 | 规模 | 说明 |
|--------|------|------|------|
| P0 | 诊断 Agent（AI 助教） | 2-3 周 | 核心，本期主体 |
| P1 | trace diff（对比两次执行） | 1 周 | 对比引擎先做确定性实现，再被诊断 Agent 复用 |
| P2 | 多框架支持（OpenAI Agents SDK） | 2 周+ | 动底层抽象，风险最高，排最后 |
| P3 | 导出 Langfuse 格式 | 0.5 周 | 低成本兼容件 |

> 相对原规划书的调整：原顺序为 P0 诊断 Agent → P1 多框架 → P2 trace diff →
> P3 Langfuse 导出。本次把 trace diff 提前到 P1，因为 compare_traces 是诊断
> Agent 的第三个工具，先做确定性对比引擎可以被 Agent 直接复用；多框架需要新写
> 采集适配器并抽象 collector 接口，成本最高、收益最不确定。

## 3. 架构

### 3.1 模块划分（新增部分）

```
agenteval/
├── diagnose/                  # 新增：诊断层（只读依赖 storage）
│   ├── __init__.py            # 导出 diagnose() / build_diagnose_graph()
│   ├── tools.py               # get_trace(摘要) / get_span / compare_traces
│   ├── prompts.py             # 教学式系统提示词 + 用户问题构建
│   ├── report.py              # 四段式报告结构（解析/渲染/校验）
│   └── graph.py               # 无状态 LangGraph ReAct 循环 + diagnose() 入口
├── web/
│   ├── diagnose_view.py       # 新增：Web 诊断页（AI 助教）
│   └── diff_view.py           # 新增：trace 对比页（P1，复用 compare_traces）
├── export/
│   └── langfuse.py            # 新增：导出 Langfuse 兼容格式（P3）
└── __init__.py                # 新增对外 API：agenteval.diagnose()
```

### 3.2 依赖方向

```
web → diagnose → storage（只读）
diagnose 不依赖 collector / replay / web
collector 完全不感知 diagnose
```

### 3.3 工具设计（修订版）

| 工具 | 行为 | 作用 |
|------|------|------|
| get_trace(trace_id) | 返回**摘要树**：每个 span 的 span_id/depth/type/name/耗时/annotation/error，不含完整 input/output | 看全局，控上下文 |
| get_span(trace_id, span_id) | 递归定位 span，返回完整 input/output/metadata（沿用 10KB 截断规则） | 看细节 |
| compare_traces(id1, id2) | 确定性 diff：按 DFS 位置对齐 span，标出状态/耗时/输出差异 + 文本摘要 | 看对比 |

### 3.4 图结构

- 无状态单 Agent，`analyze` 节点 + `call_tools` 节点组成 ReAct 循环；
- 最大工具调用次数上限（默认 8），防止烧钱；
- LLM 调用失败 / 工具异常全部转成明确中文错误，不崩溃；
- 报告为 Markdown，固定四段式：`## 概述 / ## 可疑步骤 / ## 原因分析 / ## 修改建议`。

### 3.5 入口

- Web：侧边栏新增"AI 诊断"页（选 trace + 可选对比 trace + 可选问题），
  复用 replay 的 LLM 配置（model / base_url / api_key），不新增配置入口；
- 程序 API：`agenteval.diagnose(trace_id, question=None, trace_id2=None)`；
- dogfooding：诊断过程本身以 `wrap(name="AgentEval 诊断助手")` 采集入库。

## 4. 任务拆解

### Week 1：diagnose 包（纯逻辑 + 测试）

- [x] `diagnose/tools.py`：get_trace 摘要 / get_span / compare_traces（含 `_flatten_spans`、`_find_span`、`_diff_spans`、`TOOL_SPECS`、`TOOL_DISPATCH`）
- [x] `diagnose/prompts.py`：`SYSTEM_PROMPT`（教学化 + 强制四段式 + 必须引用 span_id）+ `build_user_prompt()`
- [x] `diagnose/report.py`：`SECTIONS` / `parse_report()` / `render_report()` / `has_complete_report()`
- [x] `diagnose/graph.py`：`build_diagnose_graph(llm, max_steps)` + `diagnose(db_path, trace_id, question, trace_id2, llm, llm_factory, model_name, max_steps, run)`
- [x] `diagnose/__init__.py` 导出
- [x] `tests/test_diagnose_tools.py` / `test_diagnose_report.py` / `test_diagnose_graph.py`
- 验收：三个测试文件全过；不依赖真实 LLM API；100+ span 摘要不爆上下文。

### Week 2：对外 API + Web 诊断页 + dogfooding

- [x] `__init__.py` 新增 `agenteval.diagnose()`（复用 `_llm_factory`；handler 激活时走 `wrap` 采集）
- [x] `web/diagnose_view.py`：选 trace / 可选对比 / 可选问题 / 开始诊断 / Markdown 报告展示
- [x] `web/app.py`：导航增加"AI 诊断"
- [x] `tests/test_diagnose_view.py` + `tests/test_diagnose_api.py`
- 验收：Web 页面可生成报告；未配置 API Key 时给出明确提示；诊断本身入库（dogfooding）。

### Week 3：trace diff 页 + Langfuse 导出 + 打磨

- [x] `web/diff_view.py`：两个 trace 并排对比（复用 compare_traces）+ 差异表格
- [x] `export/langfuse.py`：`to_langfuse_payload(trace)` + `export_to_jsonl()`
- [x] README 补充 V2 使用说明（诊断页 + API + 已知限制）
- [x] 版本号升到 0.2.0；`__version__` 与 pyproject 同步
- 验收：diff 页可用；导出函数有测试；全量测试通过。

## 5. 验收标准（V2-P0）

- [x] 选中 trace 可生成四段式 Markdown 诊断报告，可疑步骤带 span_id
- [x] 大 trace（100+ span）不爆上下文（get_trace 摘要机制生效）
- [x] 诊断过程本身在 trace 列表中可见（agent_name = "AgentEval 诊断助手"）
- [x] 未配置 API Key / llm_factory 时有明确错误提示，其余功能不受影响
- [x] LLM 调用失败、工具异常、达到最大步数均不崩溃
- [x] 旧测试全部通过（Week 1-5 + UX 迭代），新测试全 mock

## 6. 已知限制（写进 README）

- 诊断 Agent 只分析本地 SQLite 中的 trace；
- 一次诊断的上下文受 `get_trace` 摘要 + `get_span` 截断控制，不会完整加载 trace；
- 报告质量依赖所配置的 LLM，模型建议支持 tool calling。

---

*本文档随 V2 进度持续更新。*
