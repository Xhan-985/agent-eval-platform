# AgentEval

> 面向学习者的 AI Agent 执行调试器。3 行代码接入 LangGraph，自动生成教学注释，支持 LLM 节点安全回放。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-WIP-orange.svg)](https://github.com/your-username/agenteval)

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
agenteval.init()

graph = build_my_langgraph()          # 你的 LangGraph
traced_graph = agenteval.wrap(graph)  # 一行包装，自动注入采集

result = traced_graph.invoke({"messages": [("user", "LangGraph 是什么？")]})
# 自动输出带教学注释的 trace
```

就这么简单，3 行代码接入。如果你的调用函数签名包含 `**kwargs`，也可以用 `@agenteval.trace` 装饰器（详见 [开发交接文档](./docs/HANDOVER.md)）。

## 示例

见 [`examples/`](./examples/) 目录：

- [`react_agent_trace.py`](./examples/react_agent_trace.py) — ReAct Agent 完整示例

## 路线图

| 版本 | 功能 | 状态 |
|------|------|------|
| v0.1.0 | 采集 + 教学注释 + LLM 节点 replay | 开发中 |
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

## 贡献

欢迎 Issue 和 PR。开发前请阅读 [开发交接文档](./docs/HANDOVER.md)。

## License

[MIT](./LICENSE)
