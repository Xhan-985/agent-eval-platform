"""AgentEval 端到端示例：ReAct 风格 Agent 的 trace 采集。

用法：
    python examples/react_agent_trace.py            # fake 模式，无需 API key
    python examples/react_agent_trace.py --real     # 真实 OpenAI 模型（需要 OPENAI_API_KEY）

演示 3 个场景：
1. 正常调用（LLM → tool → LLM）
2. tool 抛异常（error span 验证，trace 仍被完整记录）
3. 多轮调用（复用同一包装对象，每次执行生成独立 trace）
"""

from __future__ import annotations

import json
import sys
from typing import TypedDict

import agenteval


def _ensure_utf8_stdout() -> None:
    """Windows 控制台默认 GBK 编码，切换为 UTF-8 避免打印 emoji/中文崩溃。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


class State(TypedDict):
    query: str
    messages: list[str]


def _make_tools():
    """创建两个 mock tool：search（可触发错误）和 calculator。"""
    from langchain_core.tools import tool

    @tool
    def search(query: str) -> str:
        """搜索网络（mock）。query 包含 boom 时会失败，用于演示错误链路。"""
        if "boom" in query:
            raise ValueError("search backend exploded")
        return f"搜索到关于「{query}」的 3 条结果"

    @tool
    def calculator(expression: str) -> str:
        """计算形如 '1+2' 的简单表达式（mock）。"""
        parts = expression.replace(" ", "").split("+")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return str(int(parts[0]) + int(parts[1]))
        return f"无法计算：{expression}"

    return search, calculator


def build_fake_graph():
    """fake 模式：FakeListChatModel + 手写 ReAct 风格图（无需 API key）。"""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langgraph.graph import END, START, StateGraph

    search, calculator = _make_tools()
    reason_llm = FakeListChatModel(responses=["我需要先搜索。"])
    final_llm = FakeListChatModel(responses=["最终答案：42。"])

    def reason(state: State) -> dict:
        resp = reason_llm.invoke(state["query"])
        return {"messages": state["messages"] + [f"思考：{resp.content}"]}

    def act(state: State) -> dict:
        search_result = search.invoke(state["query"])
        calc_result = calculator.invoke("1+2")
        return {"messages": state["messages"] + [search_result, calc_result]}

    def final(state: State) -> dict:
        resp = final_llm.invoke(state["query"])
        return {"messages": state["messages"] + [f"回答：{resp.content}"]}

    graph = StateGraph(State)
    graph.add_node("reason", reason)
    graph.add_node("act", act)
    graph.add_node("final", final)
    graph.add_edge(START, "reason")
    graph.add_edge("reason", "act")
    graph.add_edge("act", "final")
    graph.add_edge("final", END)
    return graph.compile()


def build_real_graph():
    """real 模式：ChatOpenAI + langgraph.prebuilt.create_react_agent。"""
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    search, calculator = _make_tools()
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return create_react_agent(model, tools=[search, calculator])


def _print_spans(span, indent: int = 0) -> None:
    prefix = "  " * indent
    mark = "[ERR]" if span.get("error") else "[OK]"
    print(f"{prefix}{mark} [{span['type']}] {span['name']} — {span['annotation']}")
    for child in span.get("children", []):
        _print_spans(child, indent + 1)


def run_case(label: str, wrapped, query: str) -> None:
    """执行一个场景并打印 trace 摘要。"""
    print(f"\n=== {label} ===")
    try:
        result = wrapped.invoke(
            {"query": query, "messages": []}, config={"thread_id": label}
        )
        print("结果:", json.dumps(result, ensure_ascii=False)[:160])
    except Exception as exc:  # noqa: BLE001 —— 示例中需要演示异常场景
        print(f"执行失败（trace 仍被记录）：{type(exc).__name__}: {exc}")
    trace = agenteval.last_trace()
    print(f"trace_id: {trace['trace_id']}  status: {trace['status']}")
    _print_spans(trace["root_span"])


def main() -> None:
    _ensure_utf8_stdout()
    mode = "real" if "--real" in sys.argv else "fake"
    agenteval.init(verbose=False)
    print(f"AgentEval 示例（{mode} 模式）")
    graph = build_real_graph() if mode == "real" else build_fake_graph()

    # 复用同一个包装对象：验证每次 invoke 生成独立 trace
    wrapped = agenteval.wrap(graph)
    run_case("场景 1：正常调用", wrapped, "LangGraph 是什么？")
    run_case("场景 2：tool 抛异常", wrapped, "boom 测试")
    run_case("场景 3：多轮调用（第二次）", wrapped, "给我讲个笑话")


if __name__ == "__main__":
    main()
