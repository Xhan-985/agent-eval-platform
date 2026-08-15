# AgentEval V3 开发计划（性能分析 → 多框架）

> 版本：v3.0 | 更新时间：2026-08-15 | 分支：v3（不合并 main，除非用户明确要求）
> 依据：docs/AgentEval_PROJECT_DOC.md 11.4；docs/HANDOVER.md 8.5

## 1. 路线（重审后的顺序）

| 版本 | 功能 | 规模 | 状态 |
|------|------|------|------|
| V3-P0（0.3.0） | 性能分析 + token 成本归因 | 1-2 周 | 本期 |
| V3-P1（0.4.0） | 多框架支持（仅 OpenAI Agents SDK） | 2-4 周 | 规划中 |
| V3-P2（0.5.0） | 导出 OTLP | 0.5 周 | 规划中 |

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

## 3. V3-P1：多框架支持（OpenAI Agents SDK）— 规划

- 采集层抽象：把 trace 构建从 LangChain callback 解耦成框架无关的 span 事件流
- 新建 `collector/agents_sdk_adapter.py`
- 前置决策（开工前必须定）：
  - async 方案：a) 同步桥接（asyncio.run 包装） b) 采集器原生支持 async c) 暂缓
- 验收：同一套 Web / 诊断 / replay 对 LangGraph 与 OpenAI Agents SDK 生成的 trace 都可用

## 4. 已知限制

- 性能分析只统计已采集的数据（token 需模型返回 usage 才有值）
- 成本估算依赖单价配置，默认不展示，避免误导

---

*本文档随 V3 进度持续更新。*
