"""诊断工具（get_trace 摘要 / get_span / compare_traces）的单元测试。"""

from agenteval.diagnose.tools import compare_traces, get_span, get_trace
from agenteval.storage.db import init_db, insert_trace


def _span(
    span_id: str,
    type_: str,
    name: str,
    annotation: str = "",
    error: str | None = None,
    metadata: dict | None = None,
    children: list | None = None,
    started: str = "2026-08-15T00:00:00+00:00",
    ended: str = "2026-08-15T00:00:01+00:00",
) -> dict:
    return {
        "span_id": span_id,
        "type": type_,
        "name": name,
        "input": {"query": "LangGraph 是什么？"},
        "output": {"text": f"out-{name}"},
        "error": error,
        "annotation": annotation,
        "started_at": started,
        "ended_at": ended,
        "metadata": metadata or {},
        "children": children or [],
    }


def _trace(trace_id: str = "t1", status: str = "success", agent_name: str = "ReAct Agent") -> dict:
    root = _span(
        "s-root",
        "agent_run",
        agent_name,
        ended="2026-08-15T00:00:05+00:00",
        children=[
            _span(
                "s-llm1",
                "llm_call",
                "deepseek-v4-flash",
                annotation="Agent 正在决定下一步",
                metadata={"token_usage": {"total_tokens": 100}},
            ),
            _span(
                "s-tool",
                "tool_call",
                "search",
                annotation="Agent 调用了搜索工具",
                error="boom" if status == "error" else None,
            ),
        ],
    )
    return {
        "trace_id": trace_id,
        "created_at": "2026-08-15T00:00:00+00:00",
        "status": status,
        "framework": "langgraph",
        "agent_name": agent_name,
        "root_span": root,
    }


def _seed(db: str, trace: dict) -> None:
    init_db(db)
    insert_trace(db, trace)


def test_get_trace_returns_summary_without_full_input(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace())

    summary = get_trace(db, "t1")

    assert summary["trace_id"] == "t1"
    assert summary["agent_name"] == "ReAct Agent"
    assert summary["status"] == "success"
    assert summary["span_count"] == 3
    assert summary["total_tokens"] == 100
    assert summary["duration_ms"] == 5000
    assert summary["query_preview"] == "LangGraph 是什么？"
    assert [s["span_id"] for s in summary["spans"]] == ["s-root", "s-llm1", "s-tool"]
    # 摘要里每个 span 都不含完整 input/output
    assert all("input" not in s and "output" not in s for s in summary["spans"])
    assert summary["spans"][0]["depth"] == 0
    assert summary["spans"][1]["depth"] == 1
    assert summary["spans"][1]["annotation"] == "Agent 正在决定下一步"


def test_get_trace_unknown_id_returns_none(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace())

    assert get_trace(db, "nope") is None


def test_get_span_returns_full_detail(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace())

    span = get_span(db, "t1", "s-tool")

    assert span["span_id"] == "s-tool"
    assert span["type"] == "tool_call"
    assert span["name"] == "search"
    assert span["input"] == {"query": "LangGraph 是什么？"}
    assert span["output"] == {"text": "out-search"}


def test_get_span_unknown_id_returns_none(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace())

    assert get_span(db, "t1", "s-nope") is None


def test_get_span_unknown_trace_returns_none(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace())

    assert get_span(db, "nope", "s-root") is None


def test_compare_traces_identical_has_no_differences(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace(trace_id="t1"))
    _seed(db, _trace(trace_id="t2"))

    result = compare_traces(db, "t1", "t2")

    assert result["trace_a"]["trace_id"] == "t1"
    assert result["trace_b"]["trace_id"] == "t2"
    assert result["differences"] == []
    assert "没有显著差异" in result["summary"]


def test_compare_traces_detects_error_diff(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace(trace_id="ok", status="success"))
    _seed(db, _trace(trace_id="bad", status="error"))

    result = compare_traces(db, "ok", "bad")

    assert result["trace_a"]["status"] == "success"
    assert result["trace_b"]["status"] == "error"
    error_diffs = [d for d in result["differences"] if d["field"] == "error"]
    assert error_diffs
    assert "搜索" in result["summary"]
    assert "状态" in result["summary"]
    assert "成功" in result["summary"]
    assert "失败" in result["summary"]
    # 每条差异都带类型/名称，供页面显示可读标签（不带 UUID）
    assert error_diffs[0]["type_a"] == "tool_call"
    assert error_diffs[0]["name_a"] == "search"


def test_compare_traces_detects_duration_diff(tmp_path):
    db = str(tmp_path / "t.db")
    fast = _trace(trace_id="fast")
    slow = _trace(trace_id="slow")
    slow["root_span"]["children"][0]["ended_at"] = "2026-08-15T00:00:02+00:00"
    _seed(db, fast)
    _seed(db, slow)

    result = compare_traces(db, "fast", "slow")

    duration_diffs = [
        d for d in result["differences"] if d["field"] == "duration_ms"
    ]
    assert duration_diffs
    assert duration_diffs[0]["span_id_a"] == "s-llm1"
    assert duration_diffs[0]["value_a"] == 1000
    assert duration_diffs[0]["value_b"] == 2000


def test_compare_traces_detects_extra_span(tmp_path):
    db = str(tmp_path / "t.db")
    full = _trace(trace_id="full")
    partial = _trace(trace_id="partial")
    partial["root_span"]["children"] = partial["root_span"]["children"][:1]
    _seed(db, full)
    _seed(db, partial)

    result = compare_traces(db, "full", "partial")

    extra = [d for d in result["differences"] if d["field"] == "exists_only_in_a"]
    assert extra
    assert extra[0]["value_a"] == "工具调用 · 搜索"
    assert result["span_count_a"] == 3
    assert result["span_count_b"] == 2


def test_compare_traces_unknown_id_returns_none(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db, _trace(trace_id="t1"))

    assert compare_traces(db, "t1", "nope") is None
    assert compare_traces(db, "nope", "t1") is None
