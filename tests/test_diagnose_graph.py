"""诊断 Agent（LangGraph ReAct 循环）的单元测试（mock LLM，不依赖真实 API）。"""

import json

from langchain_core.messages import AIMessage, ToolMessage

from agenteval.diagnose.graph import build_diagnose_graph, diagnose
from agenteval.diagnose.report import has_complete_report
from agenteval.storage.db import init_db, insert_trace


def _span(
    span_id: str,
    type_: str,
    name: str,
    annotation: str = "",
    error: str | None = None,
    children: list | None = None,
) -> dict:
    return {
        "span_id": span_id,
        "type": type_,
        "name": name,
        "input": {"query": "LangGraph 是什么？"},
        "output": {"text": f"out-{name}"},
        "error": error,
        "annotation": annotation,
        "started_at": "2026-08-15T00:00:00+00:00",
        "ended_at": "2026-08-15T00:00:01+00:00",
        "metadata": {},
        "children": children or [],
    }


def _trace(trace_id: str = "t1", status: str = "success") -> dict:
    return {
        "trace_id": trace_id,
        "created_at": "2026-08-15T00:00:00+00:00",
        "status": status,
        "framework": "langgraph",
        "agent_name": "ReAct Agent",
        "root_span": _span(
            "s-root",
            "agent_run",
            "ReAct Agent",
            children=[
                _span("s-llm1", "llm_call", "deepseek-v4-flash"),
                _span(
                    "s-tool",
                    "tool_call",
                    "search",
                    error="boom" if status == "error" else None,
                ),
            ],
        ),
    }


def _seed(db: str, trace: dict) -> None:
    init_db(db)
    insert_trace(db, trace)


def _tool_call_msg(name: str, args: dict, call_id: str = "call1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": call_id, "type": "tool_call"}
        ],
    )


REPORT = (
    "## 概述\n执行整体正常。\n\n"
    "## 可疑步骤\n- s-tool 需要关注。\n\n"
    "## 原因分析\n工具返回了脏数据。\n\n"
    "## 修改建议\n给工具调用加异常处理。"
)


class _ScriptedLLM:
    """按脚本依次返回 AIMessage 的假 LLM，支持 bind_tools 契约。"""

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list = []
        self.bound_tools = None

    def bind_tools(self, specs):
        self.bound_tools = specs
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, AIMessage):
            return response
        return AIMessage(content=response)


class _FailingLLM:
    def bind_tools(self, specs):
        return self

    def invoke(self, messages):
        raise RuntimeError("api down")


def test_diagnose_runs_tool_loop_and_returns_report(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())
    llm = _ScriptedLLM(
        [_tool_call_msg("get_trace", {"trace_id": "t1"}), REPORT]
    )

    report = diagnose(db, "t1", llm=llm)

    assert has_complete_report(report)
    assert len(llm.calls) == 2
    tool_result = llm.calls[1][-1]
    assert isinstance(tool_result, ToolMessage)
    payload = json.loads(tool_result.content)
    assert payload["trace_id"] == "t1"
    assert {s["function"]["name"] for s in llm.bound_tools} == {
        "get_trace",
        "get_span",
        "compare_traces",
    }


def test_diagnose_with_question_and_compare_trace(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace(trace_id="t1"))
    _seed(db, _trace(trace_id="t2", status="error"))
    llm = _ScriptedLLM(
        [
            _tool_call_msg(
                "compare_traces",
                {"trace_id_1": "t1", "trace_id_2": "t2"},
            ),
            REPORT,
        ]
    )

    report = diagnose(db, "t1", question="为什么失败？", trace_id2="t2", llm=llm)

    assert has_complete_report(report)
    first_user_text = llm.calls[0][-1].content
    assert "为什么失败？" in first_user_text
    assert "t2" in first_user_text
    tool_result = llm.calls[1][-1]
    payload = json.loads(tool_result.content)
    assert payload["trace_a"]["trace_id"] == "t1"
    assert payload["trace_b"]["status"] == "error"


def test_diagnose_max_steps_caps_tool_calls(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())
    llm = _ScriptedLLM(
        [
            _tool_call_msg("get_trace", {"trace_id": "t1"}),
            _tool_call_msg("get_trace", {"trace_id": "t1"}),
            _tool_call_msg("get_trace", {"trace_id": "t1"}),
        ]
    )

    report = diagnose(db, "t1", llm=llm, max_steps=2)

    assert "最大工具调用次数" in report
    assert len(llm.calls) == 2


def test_diagnose_llm_error_returns_friendly_message(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())

    report = diagnose(db, "t1", llm=_FailingLLM())

    assert "诊断模型调用失败" in report
    assert "RuntimeError" in report


def test_diagnose_missing_trace_returns_error(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())

    assert "trace 不存在：nope" in diagnose(db, "nope", llm=_ScriptedLLM([]))


def test_diagnose_without_llm_returns_clear_error(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())

    report = diagnose(db, "t1")

    assert "未配置 llm_factory" in report


def test_diagnose_uses_factory_to_build_llm(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())
    created = []

    def factory(model_name):
        created.append(model_name)
        return _ScriptedLLM([REPORT])

    report = diagnose(db, "t1", llm_factory=factory, model_name="diag-model")

    assert created == ["diag-model"]
    assert has_complete_report(report)


def test_diagnose_tool_missing_data_returns_friendly_tool_result(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())
    llm = _ScriptedLLM(
        [
            _tool_call_msg(
                "get_span", {"trace_id": "t1", "span_id": "s-nope"}
            ),
            REPORT,
        ]
    )

    diagnose(db, "t1", llm=llm)

    tool_result = llm.calls[1][-1]
    assert "未找到" in tool_result.content


def test_diagnose_unknown_tool_returns_error_result(tmp_path):
    db = str(tmp_path / "d.db")
    _seed(db, _trace())
    llm = _ScriptedLLM(
        [_tool_call_msg("unknown_tool", {}), REPORT]
    )

    diagnose(db, "t1", llm=llm)

    tool_result = llm.calls[1][-1]
    assert "未知工具" in tool_result.content


def test_build_diagnose_graph_compiles():
    graph = build_diagnose_graph(llm=_ScriptedLLM([]), max_steps=3)
    assert graph is not None
