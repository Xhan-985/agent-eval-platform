# Week 2 完成情况存档

> 存档时间：2026-08-12
> 阶段目标：存储层（SQLite）+ Web 列表页（Streamlit）
> 状态：**全部完成并验证**；Week 1 示例零改动自动入库

---

## 1. 任务完成对照

| 任务 | 状态 | 说明 |
|------|------|------|
| 1. storage/schema.py | ✅ | traces 表 + 3 索引 + status 常量映射（0/1/2 + STATUS_LABELS） |
| 2. storage/db.py | ✅ | init_db / insert_trace / list_traces（状态筛选+时间倒序）/ get_trace；WAL + busy_timeout + user_version |
| 3. callback.py 补采 model_version | ✅ | 优先 llm_output.model_version，回退 invocation_params.model，取不到不报错 |
| 4. init() 建库 + experiment_id | ✅ | init(db_path, verbose, experiment_id=None)，自动创建表；不传 experiment_id 为 NULL |
| 5. _finalize_trace 入库 | ✅ | wrap/trace 执行结束自动写 SQLite，失败只告警不影响 Agent |
| 6. web/app.py | ✅ | Streamlit 主入口，支持 AGENTEVAL_DB 环境变量指定库路径 |
| 7. web/list_view.py | ✅ | 状态筛选下拉框 + 表格（时间/状态/Agent/Token/耗时/方案）+ 选中查看完整 JSON |
| 8. tests/ | ✅ | 存储 11 + metrics 7 + 持久化 5 + callback 3 + Web AppTest 2，共 28 个新增用例 |

## 2. 验收标准对照

- ✅ `pip install -e .` 后 `init()` 自动创建数据库文件与 traces 表
- ✅ `wrap(graph).invoke()` 后 trace 自动写入 SQLite（实测示例运行 2→5 条）
- ✅ `init(experiment_id="test1")` 的 experiment_id 写入数据库；不传为 NULL
- ✅ `on_llm_end` 采集 metadata.model_version（单测覆盖三个分支：llm_output / invocation_params / 缺失不报错）
- ✅ `streamlit run agenteval/web/app.py` 可访问（HTTP 200 + AppTest 无头渲染）
- ✅ 列表页显示时间、状态（文字+emoji）、agent、token、耗时、方案列
- ✅ 状态筛选可用（AppTest 验证"失败"筛选只显示 error）
- ✅ 选中 trace 可查看完整 trace_json（selectbox + st.json）
- ✅ Week 1 示例无需改代码，trace 自动入库
- ✅ 全部测试不依赖真实 LLM；68/68 通过，覆盖率 93%，ruff 0 错误

## 3. 交付文件清单

**新增（agenteval/）**

- `storage/schema.py`：SCHEMA_SQL + STATUS_SUCCESS/ERROR/RUNNING + STATUS_LABELS
- `storage/db.py`：连接管理（WAL/busy_timeout）、init_db、insert_trace、list_traces、get_trace
- `web/metrics.py`：纯计算函数（token 聚合、耗时计算、行格式化，不依赖 streamlit）
- `web/list_view.py`：列表页 UI（筛选 + 表格 + JSON 查看）
- `web/app.py`：Streamlit 主入口

**修改**

- `agenteval/__init__.py`：init 建库 + experiment_id 参数 + _finalize_trace 持久化
- `agenteval/collector/callback.py`：on_llm_end 补采 model_version
- `pyproject.toml`：新增 `web` extra（streamlit>=1.30）
- `.gitignore`：新增 `.pytest_tmp/`

**测试（tests/）**：test_schema（3）、test_db（8）、test_metrics（7）、test_persistence（5）、test_web_app（2，缺 streamlit 时自动跳过）、test_callback 增 3；新增 conftest.py 隔离测试数据库

## 4. 验证证据（2026-08-12 复核）

- pytest：**68/68 通过**；覆盖率 **93%**；ruff：**All checks passed**
- 端到端：`examples/react_agent_trace.py` 运行前后 agenteval.db 2→5 条（成功/失败/成功），示例代码零改动
- Streamlit：`streamlit run agenteval/web/app.py` 返回 HTTP 200；AppTest 确认标题、列表、状态筛选、JSON 查看正常
- 数据库细节：WAL + busy_timeout=5000 + user_version=1；created_at/status/experiment_id 三索引

## 5. 过程中处理的问题

1. **streamlit 安装**：首次因 PyPI 网络抖动失败，重试成功（1.61.1）；放入 `web` extra，不污染核心依赖
2. **use_container_width 弃用**：Streamlit 1.61 提示该参数 2025-12-31 后移除，改用 `width="stretch"`
3. **AppTest 相对路径坑**：from_file 以调用文件目录为基准，测试改用绝对路径
4. **.pytest_tmp 权限残留**：上次中断的进程留下无权限目录，影响 pytest/ruff 输出；提升权限清理并加入 .gitignore
5. **测试数据库隔离**：新增 conftest 把 init() 默认库重定向到临时目录，避免污染仓库

## 6. 已知限制

- Week 3 树状图未做：列表页目前用表格 + 完整 JSON 展示（按计划）
- 列表页无分页/搜索：trace 量大时后续补充
- `status=running` 未实际写入（当前采集是执行结束后落库，没有运行中状态回写）
- SQLite JSON1 的 `json_extract()` 路径查询已建好 JSON 列，但当前查询按整行读取，够用；有 span 级检索需求时再启用
- Web AppTest 需要安装 `web` extra（streamlit），否则该文件自动跳过
- retriever span 未采集（Week 1 已知限制延续）

## 7. Week 3 交接要点

- 实现 `web/trace_view.py`：树状图（选型已定：优先内置 `st.graphviz_chart`，备选 plotly）+ span 注释 + input/output 折叠 + 错误高亮
- 列表页"点击查看"升级为跳转树状图详情页（Streamlit multipage 或切换视图）
- 复用 storage.get_trace() 与 metrics 工具；注意大 trace 渲染性能
- Week 4 replay 的数据基础已在 Week 1-2 就绪（metadata 含 invocation_params/token_usage/model_version/tool_call_id）

## 8. 存档方式

Week 2 相关提交：

```
d221ad2 feat(storage): implement schema and CRUD
8faccf3 feat(callback): capture model_version in on_llm_end
7a69454 feat(api): integrate SQLite persistence into init and wrap
dceab24 feat(web): implement trace list page with token and duration
```

里程碑标记：`git tag week2-complete`（本报告提交后打标）。
