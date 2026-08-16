"""一键生成演示 trace：python -m agenteval demo。

用 fake 模式（FakeListChatModel + 手写 ReAct 图，无需 API key）跑 3 个场景：
正常调用、tool 抛异常（验证 error span）、多轮调用。生成的 trace 写入 SQLite，
供 Web 列表/详情/树状图/对比页直接查看，方便新用户下载后立即体验。

实现放在包内（不依赖 examples/），pip 安装的用户同样可用。
"""

from __future__ import annotations

from typing import TypedDict

import agenteval


class _State(TypedDict):
    query: str
    messages: list[str]


def build_fake_graph():
    """fake 模式 ReAct 图：reason → act（search + calculator）→ final。"""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.tools import tool
    from langgraph.graph import END, START, StateGraph

    @tool
    def search(query: str) -> str:
        """搜索网络（mock）。query 包含 boom 时抛错，用于演示错误链路。"""
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

    reason_llm = FakeListChatModel(responses=["我需要先搜索。"])
    final_llm = FakeListChatModel(responses=["最终答案：42。"])

    def reason(state: _State) -> dict:
        resp = reason_llm.invoke(state["query"])
        return {"messages": state["messages"] + [f"思考：{resp.content}"]}

    def act(state: _State) -> dict:
        search_result = search.invoke(state["query"])
        calc_result = calculator.invoke("1+2")
        return {"messages": state["messages"] + [search_result, calc_result]}

    def final(state: _State) -> dict:
        resp = final_llm.invoke(state["query"])
        return {"messages": state["messages"] + [f"回答：{resp.content}"]}

    graph = StateGraph(_State)
    graph.add_node("reason", reason)
    graph.add_node("act", act)
    graph.add_node("final", final)
    graph.add_edge(START, "reason")
    graph.add_edge("reason", "act")
    graph.add_edge("act", "final")
    graph.add_edge("final", END)
    return graph.compile()


def generate_demo_traces(
    db_path: str | None = None,
    *,
    verbose: bool = False,
) -> list[dict]:
    """生成 3 条演示 trace 并入库，返回摘要列表（trace_id / status / 问题）。

    db_path 为 None 时使用 agenteval 当前数据库（init 默认 agenteval.db）。
    """
    cases = [
        ("场景 1：正常调用", "LangGraph 是什么？"),
        ("场景 2：tool 抛异常", "boom 测试"),
        ("场景 3：多轮调用", "给我讲个笑话"),
    ]
    agenteval.init(db_path=db_path or "agenteval.db", verbose=verbose)
    graph = build_fake_graph()
    wrapped = agenteval.wrap(graph, name="ReAct 演示")

    summary: list[dict] = []
    for label, query in cases:
        input_data = {"query": query, "messages": []}
        try:
            wrapped.invoke(input_data, config={"thread_id": label})
        except Exception:  # noqa: BLE001 - 场景 2 有意演示异常，trace 仍入库
            pass
        trace = agenteval.last_trace()
        summary.append(
            {
                "label": label,
                "trace_id": trace["trace_id"],
                "status": trace["status"],
            }
        )
    return summary
