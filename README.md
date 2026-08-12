# AgentEval

> 面向学习者的 AI Agent 执行调试器。3 行代码接入 LangGraph，自动生成教学注释，支持 LLM 节点安全回放。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-MVP-orange.svg)](https://github.com/Xhan-985/agent-eval-platform)

## 为什么需要 AgentEval

2025-2026 年 AI Agent 进入生产部署爆发期，但 Gartner 报告显示 **88% 的 Agent 试点项目无法跨越生产环境鸿沟**，首要原因是缺乏可观测性与调试能力。

现有 Agent 可观测工具（LangSmith、Langfuse、Phoenix）都面向**资深工程师和企业场景**，初学者上手门槛高，且不解释"Agent 为什么这么调"。

AgentEval 面向**学习者和初学者**，让你看懂 Agent 每一步在干什么。

## 特性

- **教学化注释** — 每个 span 自动解释"这一步在干什么、为什么"，现有工具不做这个
- **安全回放** — LLM 节点可修改输入重跑，tool 节点用录播响应避免副作用（不会重复发邮件/删数据）
- **3 行代码接入** — 比现有方案更简单，降低学习者门槛
- **零配置** — `pip install` 即用，不需要 Docker、不需要装数据库

## 快速开始

### 安装

```bash
pip install agenteval
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

## 示例

见 [`examples/`](./examples/) 目录：

- [`react_agent_trace.py`](./examples/react_agent_trace.py) — ReAct Agent 完整示例（fake / real 双模式）
- [`replay_demo.py`](./examples/replay_demo.py) — 安全 replay 演示（fake / real 双模式）

## 路线图

| 版本 | 功能 | 状态 |
|------|------|------|
| v0.1.0 | 采集 + 教学注释 + LLM 节点 replay（MVP） | ✅ MVP 完成 |
| v0.2.0 | 诊断 Agent（AI 助教） | 规划中 |
| v0.3.0 | 多框架支持（OpenAI Agents SDK） | 规划中 |
| v0.4.0 | trace diff + 性能分析 | 规划中 |

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

- 只支持同步 `invoke`，不支持 `ainvoke` / `stream`（调用会明确报错）
- 只支持 LangGraph；LangChain 原生 chain、OpenAI Agents SDK 等暂不支持（见路线图 v0.3.0）
- 只支持单次串行调用，多次 invoke 请串行执行
- RAG 检索（retriever）调用暂以 node span 呈现，不单独标注

## 贡献

欢迎 Issue 和 PR。开发前请阅读 [开发交接文档](./docs/HANDOVER.md)。

## License

[MIT](./LICENSE)
