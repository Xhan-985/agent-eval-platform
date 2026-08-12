# Week 1 完成情况存档

> 存档时间：2026-08-12
> 阶段目标：LangGraph 采集 SDK + 教学注释 + 3 行代码接入 + 端到端示例（见 Week1_TASKS.md）
> 状态：**核心功能全部完成并验证**；真实模型链路（DeepSeek）已验证

---

## 1. 任务完成对照（Week1_TASKS 的 8 个任务）

| 任务 | 状态 | 说明 |
|------|------|------|
| 1 环境搭建 | ✅ | venv + 依赖安装（Python 3.14）；fake 模型跑通，真实模型链路后续补验 |
| 2 callback 机制研究 | ✅ | 实测 LangGraph 1.2.10 / langchain-core 1.5.3，产出 docs/CALLBACK_EVENTS.md |
| 3 callback handler | ✅ | 7 类事件采集 + 内部 try-except 兜底 + run_id 字符串化 |
| 4 trace 树构建 | ✅ | 嵌套树、子 span 排序、10KB/20 条截断、不可序列化对象兜底 |
| 5 教学注释 | ✅ | 5 种 span 类型中文模板，纯函数，≤2 句 |
| 6 对外 API | ✅ | init / wrap / trace / last_trace；config 合并；异常仍出 trace；ainvoke/stream 明确拒绝 |
| 7 集成测试 + 示例 | ✅ | fake 3 场景 + real（DeepSeek）3 场景全部跑通 |
| 8 边界处理 + 打磨 | ✅（大部分） | 大输入截断、多轮独立、异常不丢 trace、logging；个别边界无专门用例（见第 6 节） |

## 2. 验收清单对照（HANDOVER 附录）

- ✅ `pip install -e .` 成功，`import agenteval` 正常
- ✅ 3 行代码接入（`init()` + `wrap(graph)` + `.invoke()`）
- ✅ 输出带教学注释的嵌套 trace JSON（`verbose=True` 打印或 `last_trace()` 获取）
- ✅ error span 正确记录；tool/LLM span 的 input/output 采集
- ✅ token_usage、invocation_params、tool_call_id 采集（metadata 透出，见第 4 节修复记录）
- ✅ 示例 3 场景可运行；单测不依赖真实 LLM；覆盖率 92%（目标 ≥80%）
- ⚠️ "新用户 10 分钟跑通"未做真人实测；quickstart 的 `build_my_langgraph()` 为示意占位
- ⚠️ 加分项（文档标注非必须）：trace 保存到文件、stream 支持——未做，stream 为显式不支持

## 3. 交付文件清单

**核心模块（agenteval/）**

- `__init__.py`：对外 API（init / wrap / trace / last_trace），config 合并，_finalize_trace
- `collector/types.py`：共享数据模型（SpanState / Span / Trace）+ 截断/安全序列化工具
- `collector/callback.py`：AgentEvalCallbackHandler（chain / chat_model / llm / tool 事件）
- `collector/serializer.py`：build_trace 树构建 + serialize_to_json
- `collector/annotator.py`：教学注释生成器（纯函数）

**测试（tests/）**：test_annotator / test_callback / test_serializer / test_api，共 40 个用例

**示例（examples/）**：react_agent_trace.py（fake 免 key / real 走 DeepSeek，3 场景）

**文档（docs/）**：CALLBACK_EVENTS.md（事件调研）、WEEK1_REPORT.md（本文件）

## 4. 验证证据（2026-08-12 复核）

- pytest：**40/40 通过**；覆盖率 **92%**；ruff：**0 错误**
- wheel 构建成功：`dist/agenteval-0.1.0-py3-none-any.whl`，collector 子包与 LICENSE、元数据完整
- fake 模式示例：正常 / tool 异常 / 多轮 3 场景，退出码 0
- real 模式（DeepSeek `deepseek-v4-flash`，base_url=https://api.deepseek.com）：
  - ReAct 循环完整采集（agent → call_model → Prompt → llm_call → tools → search → 最终回答）
  - 错误链路沿 tools 节点、tool span 记录，根 trace status=error
  - metadata 探针确认：invocation_params（含工具定义）、token_usage（含 reasoning 明细）、tool_call_id 全部入库到 span metadata

## 5. 过程中发现并修复的问题

1. **文档 API 契约不一致**（README/Week1_TASKS/HANDOVER 三处旧装饰器示例）→ 统一为 `wrap()` 为主（commit f78b8f1）
2. **装饰器签名冲突**：旧 `@trace` 向无 `**kwargs` 的函数强塞 config 会 TypeError → 引入 `wrap(graph)`（WorkBuddy 先修，审查后文档统一）
3. **metadata 透出缺陷**：serializer 输出 Span 时遗漏 metadata，replay 数据（invocation_params / token_usage / tool_call_id）丢失 → Span 模型补 metadata 字段并透出（commit 765eff4，含 2 个回归测试）
4. **真实模型 401**：key 是 DeepSeek 的，却打到 OpenAI 默认端点 → base_url 改为 DeepSeek，模型默认 deepseek-v4-flash
5. **示例结果序列化崩溃**：`json.dumps(result)` 遇 HumanMessage 对象 → default=str 兜底
6. **控制台编码**：Windows GBK 控制台打印 ✓/⚠️ 崩溃 → 示例 stdout 切 UTF-8，控制台标记用 [OK]/[ERR]

## 6. 已知限制与未验证项（诚实清单）

- 只支持同步 `invoke`；`ainvoke` / `stream` / `astream` 抛 NotImplementedError（文档已声明）
- `on_retriever_*` 未实现：RAG 检索会以 node span 呈现，不会单独标注 retriever span
- `on_llm_error` / `on_tool_error` 无直接单测（共享的 `_record_error` 逻辑已测）
- `init(verbose=True)` 打印分支未直接测试
- 真实多进程 / 大 trace（40-200 span）性能未测（Week 3 可视化时关注）
- PyPI 发布未做（Week 5 计划内）
- `create_react_agent` 在 LangGraph 1.0 已弃用（迁移到 langchain.agents）；MVP 继续用 langgraph.prebuilt 并记录

## 7. Week 2 交接要点

HANDOVER 已按专家反馈更新 schema 设计（commit 37d81ee），Week 2 需实现：

- `storage/db.py` + `storage/schema.py`：traces 表（status INTEGER 0/1/2、trace_json JSON、experiment_id）+ 索引（created_at DESC / status / experiment_id）
- 落地 SQLite 细节：`PRAGMA journal_mode=WAL`、`busy_timeout`、`user_version`（schema 版本）
- `web/app.py` + `web/list_view.py`：Streamlit 列表页（时间、状态、Agent 名、总 token、总耗时）
- `init()` 新增 `experiment_id` 参数（V2 方案对比预留，MVP 不暴露 UI）
- `on_llm_end` 补充采集 `model_version` 到 span metadata
- 存储接入点：`wrap()`/`trace` 的 `_finalize_trace` 改为写入 SQLite（保留 `last_trace()` 行为）

## 8. 存档方式

Week 1 相关提交（按时间序）：

```
f78b8f1 docs: unify wrap() API contract and version calibers across docs
2276501 feat(collector): implement Week 1 trace collection SDK
648e3da test(callback): cover token_usage capture in on_llm_end
b5cab37 chore(example): load .env for real mode, note create_react_agent deprecation
765eff4 fix(serializer): expose span metadata in trace output
37d81ee docs: update Week 2 schema based on expert review（Week 2 设计，并入存档上下文）
```

里程碑标记：`git tag week1-complete`（本报告提交后打标）。
