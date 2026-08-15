"""无状态诊断 Agent：LangGraph ReAct 循环（吃自己的狗粮）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .tools import TOOL_DISPATCH, TOOL_SPECS, get_trace

__all__ = ["DiagnoseState", "build_diagnose_graph", "diagnose"]


class DiagnoseState(TypedDict, total=False):
    """诊断图状态：只携带本次分析所需数据，无跨次 Memory。"""

    db_path: str
    trace_id: str
    trace_id2: str | None
    question: str | None
    messages: list[Any]
    steps: int
    report: str | None
    error: str | None


def build_diagnose_graph(llm: Any, max_steps: int = 8) -> Any:
    """构建无状态诊断图：analyze（LLM 决策）↔ call_tools（执行工具）。"""

    def analyze(state: DiagnoseState) -> dict[str, Any]:
        messages = list(state.get("messages") or [])
        steps = int(state.get("steps") or 0) + 1
        try:
            out = llm.bind_tools(TOOL_SPECS).invoke(messages)
        except Exception as exc:  # noqa: BLE001 —— 诊断失败要提示而不是崩溃
            return {"error": f"诊断模型调用失败：{type(exc).__name__}: {exc}"}
        next_messages = [*messages, out]
        if getattr(out, "tool_calls", None):
            if steps >= max_steps:
                return {
                    "messages": next_messages,
                    "steps": steps,
                    "error": (
                        f"已达到最大工具调用次数（{max_steps}），"
                        "诊断未完成，请简化问题后重试。"
                    ),
                }
            return {"messages": next_messages, "steps": steps}
        content = getattr(out, "content", None)
        if isinstance(content, str) and content.strip():
            return {"messages": next_messages, "steps": steps, "report": content}
        return {
            "messages": next_messages,
            "steps": steps,
            "error": "诊断模型未返回报告内容",
        }

    def call_tools(state: DiagnoseState) -> dict[str, Any]:
        messages = list(state.get("messages") or [])
        last = messages[-1]
        next_messages = list(messages)
        for tool_call in getattr(last, "tool_calls", []) or []:
            name = tool_call.get("name", "")
            args = tool_call.get("args") or {}
            fn = TOOL_DISPATCH.get(name)
            if fn is None:
                result = {"error": f"未知工具：{name}"}
            else:
                try:
                    result = fn(db_path=state["db_path"], **args)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": f"{type(exc).__name__}: {exc}"}
                if result is None:
                    result = {"error": f"{name} 未找到对应数据"}
            next_messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False, default=str),
                    tool_call_id=tool_call.get("id", ""),
                )
            )
        return {"messages": next_messages}

    def route(state: DiagnoseState) -> str:
        if state.get("error") or state.get("report"):
            return "finish"
        last = (state.get("messages") or [])[-1]
        if getattr(last, "tool_calls", None):
            return "call_tools"
        return "finish"

    graph = StateGraph(DiagnoseState)
    graph.add_node("分析", analyze)
    graph.add_node("调用工具", call_tools)
    graph.add_edge(START, "分析")
    graph.add_conditional_edges(
        "分析",
        route,
        {"call_tools": "调用工具", "finish": END},
    )
    graph.add_edge("调用工具", "分析")
    return graph.compile()


def diagnose(
    db_path: str,
    trace_id: str,
    question: str | None = None,
    trace_id2: str | None = None,
    llm: Any | None = None,
    llm_factory: Callable[[str], Any] | None = None,
    model_name: str = "diagnose",
    max_steps: int = 8,
    run: Callable[[Any, dict[str, Any]], dict[str, Any]] | None = None,
) -> str:
    """对一条（或两条）trace 运行无状态诊断 Agent，返回 Markdown 报告。

    失败（trace 不存在 / 未配置模型 / LLM 调用异常 / 达到步数上限）时返回
    明确中文错误文本，不抛异常。run 参数可注入自定义执行器（用于 dogfooding）。
    """
    if get_trace(db_path, trace_id) is None:
        return f"trace 不存在：{trace_id}"
    if trace_id2 and get_trace(db_path, trace_id2) is None:
        return f"对比 trace 不存在：{trace_id2}"
    if llm is None:
        if llm_factory is None:
            return (
                "未配置 llm_factory，请先调用 agenteval.init(llm_factory=...) "
                "或在 Web 侧边栏配置 API Key"
            )
        try:
            llm = llm_factory(model_name)
        except Exception as exc:  # noqa: BLE001
            return f"创建诊断模型失败：{type(exc).__name__}: {exc}"

    graph = build_diagnose_graph(llm, max_steps=max_steps)
    initial: dict[str, Any] = {
        "db_path": db_path,
        "trace_id": trace_id,
        "trace_id2": trace_id2,
        "question": question,
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=build_user_prompt(trace_id, question, trace_id2)),
        ],
        "steps": 0,
    }
    runner = run or (lambda graph_, state: graph_.invoke(state))
    result = runner(graph, initial)
    report = result.get("report")
    if report:
        return report
    return result.get("error") or "诊断失败：未生成报告"
