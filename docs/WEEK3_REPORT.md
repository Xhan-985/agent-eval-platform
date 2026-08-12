# Week 3 完成情况存档

> 存档时间：2026-08-12
> 阶段目标：trace 树状图可视化 + 列表 → 详情导航
> 状态：**全部完成并验证**；Week 2 列表页功能不受影响

---

## 1. 任务完成对照

| 任务 | 状态 | 说明 |
|------|------|------|
| 1. web/trace_view.py — build_dot() | ✅ | trace JSON → graphviz DOT 字符串（纯函数）；图标/名称/注释/耗时节点 + 红色错误高亮 + parent→child 箭头 |
| 1. web/trace_view.py — render_trace() | ✅ | st.graphviz_chart 渲染 + span 选择器 + input/output 折叠（st.expander + st.json） |
| 2. app.py 详情路由 | ✅ | session_state 记录 selected_trace_id；列表/详情两页切换 + "← 返回列表"按钮 |
| 3. list_view.py 行可点击 | ✅ | 每行"查看详情"按钮进入详情页，保留 Week 2 表格/筛选 |
| 4. tests/test_trace_view.py | ✅ | 12 个用例（DOT 结构、图标、高亮、截断、转义、中文、时长、缺失 root、render 渲染） |

## 2. 验收标准对照

- ✅ 列表页点击 trace 进入详情页（AppTest 双向导航测试）
- ✅ 详情页展示 graphviz 树状图（st.graphviz_chart，AppTest 断言元素存在）
- ✅ 节点显示：类型图标（🤖/📦/🔵/🔧/❌）+ 名称 + 注释（≤60 字截断）+ 耗时（format_duration）
- ✅ error span 红色高亮（fillcolor=#fca5a5）
- ✅ 点击节点查看 input/output（图下方 span 选择器 + 两个 expander）
- ✅ 树结构正确（"parent" -> "child"; 箭头）
- ✅ 中文正常显示（DOT UTF-8，单测断言）
- ✅ tests/test_trace_view.py 12/12 通过
- ✅ Week 2 列表页功能不受影响（原列表/筛选测试仍通过）

## 3. 交付文件清单

**新增**

- `web/trace_view.py`：build_dot（DOT 生成）、render_trace（详情 UI）、flatten_spans、_dot_escape/_truncate 等辅助函数
- `tests/test_trace_view.py`：12 个单元/AppTest 用例

**修改**

- `web/app.py`：session_state 路由（列表 ↔ 详情）+ 返回按钮 + trace 不存在兜底
- `web/list_view.py`：新增每行"查看详情"按钮导航；移除原"完整 JSON 查看"（升级为详情页）
- `tests/test_web_app.py`：新增导航测试 2 个（进详情 / 返回列表）

## 4. 验证证据（2026-08-12 复核）

- pytest：**82/82 通过**；覆盖率 **93%**；ruff：**All checks passed**
- 详情页覆盖率：app.py 92%、trace_view.py 96%、list_view.py 86%
- `streamlit run agenteval/web/app.py` HTTP 200 冒烟通过
- AppTest 无头验证：列表 → 查看详情 → 树状图 + span 选择器 + expander；返回列表

## 5. 过程中处理的问题

1. **AppTest 按钮点击不生效**：streamlit 1.61 的 `button.click()` 后需显式 `.run()`，spike 最小复现确认后修复测试
2. **错误 span 图标覆盖**：error span 按设计图标为 ❌（覆盖原类型图标），测试 fixture 补一个正常 tool span 验证 🔧
3. **截断语义**：注释截断为 57 字 + "..."（ANNOTATION_MAX_CHARS-3），测试按精确边界断言
4. **stdin 管道编码**：heredoc 经 PowerShell 管道会转码，中文标签匹配改用 pytest 文件测试（UTF-8 源文件）
5. **graphviz 节点不可点击**：Streamlit 图组件不支持节点点击事件，详情用图下方 span 选择器实现（与 Week 2 交互风格一致）

## 6. 已知限制

- 树状图不支持浏览器端节点点击（Streamlit 组件限制），用 span 选择器替代
- 大 trace（40+ span）的 DOT 渲染性能未实测（fontsize 10 + nodesep/ranksep 已做紧凑处理）
- 详情页无直接 URL 定位（刷新回到列表）
- retriever span 未采集（Week 1 已知限制延续）

## 7. Week 4 交接要点

- 实现 `replay/runner.py` + `replay/policy.py` + `web/replay_view.py`：LLM 节点真实重跑、tool 节点录播响应
- replay 数据基础已就绪：span metadata 含 invocation_params / token_usage / model_version / tool_call_id / messages
- Week 4 开工前回看 CODEX_REVIEW.md 第 3.5 条：先验证 LangGraph checkpoint/time-travel，再决定 replay 底层
- 详情页 span 选择器可复用为 replay 的目标 span 选择入口

## 8. 存档方式

Week 3 相关提交：

```
6e96150 feat(web): implement trace tree visualization with graphviz
44c82be feat(web): add trace detail page navigation
```

里程碑标记：`git tag week3-complete`（本报告提交后打标）。
