# AgentEval

> 面向学习者的 AI Agent 执行调试器。3 行代码接入 LangGraph，自动生成教学注释，支持 LLM 节点安全回放。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-v2-orange.svg)](https://github.com/Xhan-985/agent-eval-platform)

## 为什么需要 AgentEval

2025-2026 年 AI Agent 进入生产部署爆发期，但 Gartner 报告显示 **88% 的 Agent 试点项目无法跨越生产环境鸿沟**，首要原因是缺乏可观测性与调试能力。

现有 Agent 可观测工具（LangSmith、Langfuse、Phoenix）都面向**资深工程师和企业场景**，初学者上手门槛高，且不解释"Agent 为什么这么调"。

AgentEval 面向**学习者和初学者**，让你看懂 Agent 每一步在干什么。

## 特性

- **教学化注释** — 每个 span 自动解释"这一步在干什么、为什么"，现有工具不做这个
- **安全回放** — LLM 节点可修改输入重跑，tool 节点用录播响应避免副作用（不会重复发邮件/删数据）
- **AI 诊断（V2）** — 选中一条 trace，由无状态诊断 Agent（LangGraph 实现，吃自己的狗粮）生成自然语言诊断报告：哪一步可能出错、为什么、怎么改
- **Trace 对比（V2）** — 两次执行并排 diff，定位"以前能跑现在不能"
- **3 行代码接入** — 比现有方案更简单，降低学习者门槛
- **零配置** — `pip install` 即用，不需要 Docker、不需要装数据库

## 快速开始

### 安装

```bash
# 推荐：PyPI 安装（含 Web 界面与示例依赖）
pip install "agenteval-debugger[web,examples]"

# 或从源码安装
git clone https://github.com/Xhan-985/agent-eval-platform.git
cd agent-eval-platform
pip install -e ".[web,examples]"
```

只使用 SDK（不打开 Web 界面）时 `pip install agenteval-debugger` 即可；`[web]` 用于页面，`[examples]` 用于运行示例。

> 💡 **推荐在独立虚拟环境中安装**，避免与机器上已有的包（如 TensorFlow、旧版 protobuf 等）产生依赖冲突：
>
> ```powershell
> # Windows
> python -m venv agenteval-venv
> agenteval-venv\Scripts\activate
> pip install "agenteval-debugger[web,examples]"
> ```
>
> ```bash
> # macOS / Linux
> python -m venv agenteval-venv
> source agenteval-venv/bin/activate
> pip install "agenteval-debugger[web,examples]"
> ```
>
> 国内网络环境可用镜像加速（清华源示例）：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "agenteval-debugger[web,examples]"`

### 30 秒体验：一键生成演示数据

不想先接自己的 Agent？一条命令生成 3 条演示 trace（fake 模式，**无需 API key**）：

```bash
agenteval-demo        # 或 python -m agenteval demo
```

输出示例：

```text
已生成 3 条演示 trace：
  [成功] 场景 1：正常调用      trace_id: 003e47a7…
  [失败] 场景 2：tool 抛异常   trace_id: 9a3ddbf2…
  [成功] 场景 3：多轮调用      trace_id: 21b53df1…
```

然后启动 Web 界面即可查看完整列表 / 树状图 / 对比：

```bash
agenteval-web        # 或 python -m agenteval web
```

### 接入你的 LangGraph Agent

```python
import agenteval
agenteval.init(verbose=True)  # verbose=True 时自动打印带注释的 trace

graph = build_my_langgraph()          # 你的 LangGraph
traced_graph = agenteval.wrap(graph)  # 一行包装，自动注入采集

result = traced_graph.invoke({"messages": [("user", "LangGraph 是什么？")]})
# 自动输出带教学注释的 trace
```

就这么简单，3 行代码接入。默认静默采集，任何时刻可用 `agenteval.last_trace()` 拿到最近一次执行的 trace JSON。如果你的调用函数签名包含 `**kwargs`，也可以用 `@agenteval.trace` 装饰器（详见 [开发交接文档](./docs/HANDOVER.md)）。

**给 Agent 命名**：列表页的"Agent"列默认显示 LangGraph 图的默认名（`LangGraph`），用 `agenteval.wrap(graph, name="我的搜索Agent")` 可以给每次执行的 agent 起个有意义的名字，方便在列表里区分不同任务。

### 接入你的 OpenAI Agents SDK Agent（V3）

OpenAI Agents SDK 是 async 生态，AgentEval 通过它的 TracingProcessor 采集，
不用改你的 Agent 代码，只需在启动时调用一次：

```bash
pip install "agenteval-debugger[agents-sdk]"
```

```python
import asyncio
import agenteval
from agents import Agent, Runner

agenteval.init(agents_sdk=True)   # 注册采集器，进程内所有 Runner.run() 自动入库

async def main():
    agent = Agent(name="学习助手", instructions="你是中文学习助手。")
    result = await Runner.run(agent, "用一句话解释什么是 Agent？")
    print(result.final_output)

asyncio.run(main())
```

采集到的 trace 与 LangGraph 完全同构：Web 列表/详情/树状图/诊断/replay 都能直接用。
完整示例见 [`examples/agents_sdk_demo.py`](./examples/agents_sdk_demo.py)。

> ℹ️ 隐私说明：`init(agents_sdk=True)` 会把 SDK 默认上传 OpenAI 平台的导出器替换为
> 本地入库，trace 只写入本地 `agenteval.db`，不会上传到任何平台。

### 安全 replay（LLM 节点重跑）

Web 详情页选中 LLM span 后，可修改 input 并重跑；tool span 只回放录播响应，**不会真实执行**（避免发邮件、写库等副作用）。

```python
import agenteval
from langchain_openai import ChatOpenAI

agenteval.init(
    verbose=True,
    llm_factory=lambda model_name: ChatOpenAI(model=model_name, api_key="sk-..."),
)
```

`llm_factory` 接收模型名并返回一个 ChatModel 实例。不配置时 replay 会给出明确提示，其他功能不受影响。

### AI 诊断（V2）

对任意一条（或两条）trace 运行诊断 Agent，输出中文 Markdown 报告：

```python
import agenteval
from langchain_openai import ChatOpenAI

agenteval.init(
    llm_factory=lambda model_name: ChatOpenAI(
        model=model_name,
        base_url="https://api.deepseek.com",
        api_key="sk-...",
    ),
)

report = agenteval.diagnose("你的-trace-id", question="为什么这一步报错？")
print(report)
```

也可以带第二个 trace_id 让诊断 Agent 做对比诊断（内部使用 compare_traces 工具）。
Web 侧边栏"AI 诊断"页提供同样的能力，无需写代码。**要求模型支持 tool calling**
（DeepSeek / OpenAI 兼容模型均可）；未配置 `llm_factory` 时页面和 API 都会给出明确提示。

### 导出 Langfuse 格式（V2）

```python
from agenteval.export.langfuse import export_to_jsonl

export_to_jsonl("agenteval.db", "你的-trace-id", "export.jsonl")
```

生成 Langfuse 字段命名（traces + observations）的 JSONL 文件，方便迁移到 Langfuse 生态。

### 导出 OTLP（V3）

把 trace 导出为标准 OpenTelemetry OTLP/HTTP JSON 格式，可接入 Jaeger、Grafana
Tempo 等可观测平台。零依赖实现，无需安装 opentelemetry SDK：

```python
from agenteval.export.otlp import export_otlp_json, send_otlp_http

# 1) 导出为 JSON 文件（可直接用 Jaeger 等工具导入）
export_otlp_json("agenteval.db", "你的-trace-id", "trace.otlp.json")

# 2) 直接推送到 OTLP/HTTP 端点（本地 Jaeger Collector 默认 4318）
send_otlp_http("agenteval.db", "你的-trace-id", "http://localhost:4318/v1/traces")
```

llm_call span 附带 `gen_ai.*` 语义属性（模型名 / input / output / total tokens），
error span 标记 `status.code=ERROR` 并生成 exception 事件。

### 使用 DeepSeek / OpenAI 兼容 API

OpenAI 兼容接口只需配置 `base_url`：

```python
agenteval.init(
    llm_factory=lambda model_name: ChatOpenAI(
        model=model_name,
        base_url="https://api.deepseek.com",  # 默认 OpenAI 端点可省略
        api_key="sk-...",
    ),
)
```

DeepSeek 模型名形如 `deepseek-v4-flash` / `deepseek-v4-pro`。API key 建议放环境变量 `OPENAI_API_KEY` 或本地 `.env`（已被 gitignore），不要写进代码。

`agenteval-web` 启动时会自动读取当前目录的 `.env`；也可以把
`OPENAI_BASE_URL=https://api.deepseek.com` 写进 `.env`，Web 侧边栏会自动带出，
避免每次手动改 Base URL。

### 启动 Web 界面

安装时带上 `[web]` 依赖后，一条命令即可打开可视化页面：

```bash
agenteval-web          # 或 python -m agenteval web
```

浏览器会自动打开 http://localhost:8501，页面包含：

- **仪表盘**：落地首页，KPI 概览（Trace 总数 / 成功率 / 总 Token / 平均耗时 / 错误数）、近 14 天趋势图、状态分布、最近 Trace 表
- **列表页**：可交互表格（行选中进详情），支持按 Agent / 状态 / 关键词搜索与分页
- **详情页**：顶部摘要卡（状态徽标、Agent、模型、总耗时、总 Token、span 数）+ 三视图 tabs
  - **时间线**：横向瀑布图，按 span 起止与耗时排布、按类型着色、出错节点标红
  - **调用树**：graphviz 树状图，节点带类型图标、教学注释、耗时
  - **Span 列表**：平铺表，按类型/错误筛选
- **span 详情**：下拉选 span 查看全文注释、耗时、token 用量、可折叠 input / output
- **replay 面板**：LLM span 可改输入重跑（结构化原/新 output 对比 + replay 历史），tool span 显示录播响应（不真实执行）
- **AI 诊断页（V2）**：选一条 trace（可选第二条做对比、可选问题），一键生成四段式诊断报告（概述 / 可疑步骤 / 原因分析 / 修改建议），可疑步骤带 span_id；诊断过程本身会作为一条 trace 入库（agent_name = "AgentEval 诊断助手"）
- **Trace 对比页（V2）**：两个 trace 并排选择，展示状态 / 耗时 / span 级差异表格
- **性能分析（V3）**：详情页"性能"tab，span 耗时/token 归因排行（占比 + 慢节点 + 可选成本估算），仪表盘显示最慢单次执行

注意事项：

- 页面默认读取**当前目录**的 `agenteval.db`（与运行 Agent 时一致）；如果 Agent 在其他目录运行，用环境变量 `AGENTEVAL_DB=/path/to/agenteval.db` 指定，或在页面侧边栏手动填写数据库路径
- replay 的模型配置在页面侧边栏（模型名 / API Base URL / API Key），也可以用代码里的 `init(llm_factory=...)`
- 界面为中文、单机本地工具（Streamlit），不会上传任何数据
- 建议使用**最新版 Chrome / Edge / 夸克**浏览器访问页面；个别旧版或第三方浏览器内核与
  Streamlit 前端存在兼容问题（可能报 `removeChild` 前端错误），升级浏览器或换浏览器即可

## 示例

见 [`examples/`](./examples/) 目录：

- [`react_agent_trace.py`](./examples/react_agent_trace.py) — ReAct Agent 完整示例（fake / real 双模式）
- [`replay_demo.py`](./examples/replay_demo.py) — 安全 replay 演示（fake / real 双模式）
- [`agents_sdk_demo.py`](./examples/agents_sdk_demo.py) — OpenAI Agents SDK 接入示例

## 路线图

| 版本 | 功能 | 状态 |
|------|------|------|
| v0.1.0 | 采集 + 教学注释 + LLM 节点 replay（MVP） | ✅ MVP 完成 |
| v0.2.0 | 诊断 Agent（AI 助教）+ trace diff + Langfuse 导出 | ✅ 完成 |
| v0.3.0 | 性能分析 + token 成本归因 | ✅ 完成 |
| v0.4.0 | 多框架支持（OpenAI Agents SDK） | ✅ 完成 |
| v0.5.0 | 导出 OTLP | ✅ 完成 |

## 适合谁

- **Agent 学习者**：刚学 LangGraph，想看懂 Agent 执行过程
- **教学者**：给学生演示 Agent 工作原理
- **初学者调试**：Agent 出错时定位是哪一步的问题

## 不适合谁

- 企业级生产监控（用 [Langfuse](https://github.com/langfuse/langfuse)）
- 资深工程师的 OTel 工具链（用 [Phoenix](https://github.com/Arize-ai/phoenix)）

## 与现有工具对比

| 能力 | Langfuse | Phoenix | AgentEval |
|------|----------|---------|-----------|
| 开源 | ✅ | ✅ | ✅ |
| 教学化注释 | ❌ | ❌ | ✅ |
| 面向学习者 | ❌ | ❌ | ✅ |
| 安全 replay | 部分 | ❌ | ✅ |
| 3 行代码接入 | 5+ 行 | 5+ 行 | ✅ |
| 零配置 | 需 Docker | 需配置 | pip install 即用 |

## 已知限制

- LangGraph 路径只支持同步 `invoke`，不支持 `ainvoke` / `stream`（调用会明确报错）；OpenAI Agents SDK 路径原生支持 async
- 支持 LangGraph 与 OpenAI Agents SDK；LangChain 原生 chain 等暂不支持
- 只支持单次串行调用，多次 invoke 请串行执行
- RAG 检索（retriever）调用暂以 node span 呈现，不单独标注
- 诊断 Agent 只分析本地 SQLite 中的 trace；报告质量依赖所配置的模型，模型需支持 tool calling

## 贡献

欢迎 Issue 和 PR。开发前请阅读 [开发交接文档](./docs/HANDOVER.md)。

## License

[MIT](./LICENSE)
