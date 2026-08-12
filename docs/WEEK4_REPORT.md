# Week 4 完成情况存档

> 存档时间：2026-08-12
> 阶段目标：安全 replay（LLM 真实重跑 / tool 录播响应）+ 详情页集成
> 状态：**全部完成并验证**（含真实 DeepSeek 端到端 replay）；WorkBuddy 提交已审查无阻塞问题

---

## 1. 任务完成对照

| 任务 | 状态 | 说明 |
|------|------|------|
| 1. replay/policy.py | ✅ | REPLAYABLE/RECORDED/NOT_REPLAYABLE + get_replay_policy（realtime/recorded/not_supported） |
| 2. replay/runner.py | ✅ | replay_span：LLM 真实重跑（消息归一化 + 模型 id 解析）、tool 录播、其他抛 NotReplayableError；异常进 error 字段不崩溃 |
| 3. __init__.py llm_factory | ✅ | init(llm_factory=callable)，不配置时 replay 给明确提示，其余功能不受影响 |
| 4. web/replay_view.py | ✅ | 可编辑 input + replay 按钮 + 原/新 output 对比（灰/绿）+ 录播警告 |
| 5. 详情页集成 | ✅ | trace_view 选中 span 后渲染 replay 面板 |
| 6. tests | ✅ | policy 5 + runner 9 + replay_view AppTest 6 + api 1 + web_app 侧边栏 2 |

## 2. WorkBuddy 新增提交审查（2c2a9e6）

**内容**：app.py 侧边栏新增 Replay LLM 配置（模型名 / API Base URL / API Key），有 key 时用懒加载 ChatOpenAI 工厂调用 `agenteval.init(llm_factory=...)`；fake 模式 span 回退到侧边栏模型名。

**审查结论：无阻塞问题**。设计合理：工厂懒加载（渲染页面不调 API）、key 用 password 输入不落盘、fake span 回退模型名。

**审查后处理**：
- 修复 ruff N806 风格问题（`_FAKE_NAMES` → `fake_names`）
- 补充 2 个 AppTest：侧边栏 4 个配置输入渲染正常；填入 API Key 后 `agenteval._llm_factory` 被注册

**非阻塞观察（记录不修改）**：DeepSeek 用户需同时改 base_url 和模型名（帮助文案只提了 base_url）；Streamlit 每次 rerun 会重新 init（web 场景可接受）。

## 3. 验收标准对照

- ✅ LLM span 可改 input 并 replay 返回新 output（单测 + **真实 DeepSeek 端到端**：原"我来帮你搜索…"→ 新 output 为追加问题后的真实回答）
- ✅ tool span 显示录播响应，不真实执行（测试断言 llm_factory 未被调用）
- ✅ node/agent_run 显示"不支持 replay"
- ✅ 对比展示原 output（灰）vs 新 output（绿高亮）
- ✅ 未配置 llm_factory 有明确提示（"请先调用 agenteval.init(llm_factory=...)"）
- ✅ replay 异常不崩溃（TimeoutError 进 error 字段，UI st.error 展示）
- ✅ tests 全部通过；Week 1-3 功能不受影响

## 4. 真实验证发现并修复的两个缺陷（均有回归测试）

1. **LLM 输入格式**：`llm.invoke({"messages": [...]})` 对 ChatOpenAI 非法 → runner 新增 `_normalize_llm_input`，把 dict/消息 dict 列表归一化为 BaseMessage 列表（human/ai/system/tool 类型映射）
2. **模型 id 解析**：`metadata.model_name` 是类名 "ChatOpenAI"，真实模型 id 在 `invocation_params.model` → runner 新增 `_resolve_model_name` 优先取 invocation_params

## 5. 验证证据（2026-08-12 复核）

- pytest：**105/105 通过**；覆盖率 **93%**；ruff：**All checks passed**
- 真实 replay（DeepSeek deepseek-v4-flash）：模型 id 解析正确、is_recorded=False、error=None、新 output 与原文不同
- AppTest：replay 面板 6 用例（可编辑输入、对比展示、录播警告、不支持提示、JSON 解析错误、缺 factory 提示）

## 6. 已知限制

- replay 只重跑单个 LLM 节点，不重跑整条 trace（Week 4 范围；整图 replay 可用 LangGraph checkpoint，见 CODEX_REVIEW 3.5）
- 温度等参数未从 invocation_params 透传给工厂（工厂只收 model_name；需要时由用户闭包配置）
- 侧边栏模型名默认 gpt-4o-mini，用 DeepSeek 时需手动改
- retriever span 未采集（Week 1 已知限制延续）

## 7. Week 5 交接要点

- README 完善（replay 用法 + llm_factory 示例 + 侧边栏说明）
- 端到端示例更新（演示 replay）与性能检查（大 trace）
- PyPI 发布准备（wheel 验证已做过，补 `python -m build` 与发布清单）
- 社区推广材料（掘金/Reddit 草稿）

## 8. 存档方式

Week 4 相关提交：

```
8623b01 feat(replay): implement replay policy and runner
94c909c feat(api): add llm_factory parameter to init
c1c3021 feat(web): implement replay panel with output comparison
2c2a9e6 feat(web): add replay LLM config sidebar with base_url support（WorkBuddy，已审查）
```

里程碑标记：`git tag week4-complete`（本报告提交后打标）。
