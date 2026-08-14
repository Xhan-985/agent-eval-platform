"""trace 树状图（graphviz DOT 生成 + 详情页）的单元测试。"""

import time

from agenteval.web.trace_view import build_dot, flatten_spans
from agenteval.web.tree_svg import build_svg


def _span(
    span_id,
    span_type,
    name,
    annotation="",
    error=None,
    started="2026-08-12T00:00:00+00:00",
    ended="2026-08-12T00:00:00.500000+00:00",
    children=None,
):
    return {
        "span_id": span_id,
        "type": span_type,
        "name": name,
        "input": {},
        "output": {},
        "error": error,
        "annotation": annotation,
        "started_at": started,
        "ended_at": ended,
        "metadata": {},
        "children": children or [],
    }


def _trace():
    return {
        "trace_id": "t1",
        "created_at": "2026-08-12T00:00:00+00:00",
        "status": "success",
        "framework": "langgraph",
        "agent_name": "LangGraph",
        "root_span": _span(
            "root",
            "agent_run",
            "LangGraph",
            annotation="这是 Agent 的一次完整执行",
            children=[
                _span("llm1", "llm_call", "gpt-4o-mini", annotation="模型调用"),
                _span(
                    "tool1",
                    "tool_call",
                    "search",
                    annotation="搜索信息",
                    error="boom",
                ),
                _span("calc1", "tool_call", "calculator", annotation="计算"),
            ],
        ),
    }


def test_build_dot_is_valid_shell():
    dot = build_dot(_trace())
    assert dot.startswith("digraph trace {")
    assert dot.endswith("}")
    assert 'rankdir="LR"' in dot
    assert 'arrowhead="normal"' in dot


def test_build_dot_contains_all_nodes_and_edges():
    dot = build_dot(_trace())
    assert '"root"' in dot
    assert '"llm1"' in dot
    assert '"tool1"' in dot
    assert '"root" -> "llm1"' in dot
    assert '"root" -> "tool1"' in dot


def test_build_dot_node_count_matches_spans():
    dot = build_dot(_trace())
    assert dot.count("[label=") == 4


def test_build_dot_marks_error_span_red():
    dot = build_dot(_trace())
    assert 'fillcolor="#fca5a5"' in dot


def test_build_dot_shows_icons():
    dot = build_dot(_trace())
    assert "🔵" in dot  # llm_call
    assert "🔧" in dot  # tool_call
    assert "🤖" in dot  # agent_run
    assert "❌" in dot  # error span


def test_build_dot_truncates_long_annotation():
    trace = _trace()
    trace["root_span"]["children"][0]["annotation"] = "长" * 100
    dot = build_dot(trace)
    assert "长" * 60 not in dot
    assert "长" * 57 in dot
    assert "..." in dot


def test_build_dot_preserves_chinese():
    dot = build_dot(_trace())
    assert "这是 Agent 的一次完整执行" in dot
    assert "模型调用" in dot


def test_build_dot_shows_duration():
    dot = build_dot(_trace())
    assert "500ms" in dot


def test_build_dot_escapes_quotes_and_backslashes():
    trace = _trace()
    trace["root_span"]["children"][0]["name"] = 'a"b\\c'
    dot = build_dot(trace)
    assert 'a\\"b\\\\c' in dot


def test_build_dot_handles_missing_root():
    dot = build_dot({"trace_id": "x"})
    assert dot.startswith("digraph trace {")
    assert "[label=" not in dot


def test_build_dot_large_trace_renders_quickly():
    children = [
        _span(f"n{i}", "node", f"node-{i}", annotation="这是一个较长的教学注释用于测试性能")
        for i in range(120)
    ]
    trace = {
        "root_span": _span("root", "agent_run", "LangGraph", children=children)
    }
    start = time.perf_counter()
    dot = build_dot(trace)
    elapsed = time.perf_counter() - start
    assert dot.count("[label=") == 121
    assert elapsed < 5.0


def test_flatten_spans_returns_all_spans():
    spans = flatten_spans(_trace())
    assert [s["span_id"] for s in spans] == ["root", "llm1", "tool1", "calc1"]


def test_build_svg_contains_arrow_marker():
    svg = build_svg(_trace())
    assert "<marker" in svg
    assert 'marker-end="url(#arrow)"' in svg


def test_build_svg_edge_count_matches_span_count():
    svg = build_svg(_trace())
    assert svg.count('marker-end="url(#arrow)"') == 3  # 4 个 span，3 条边


def test_build_svg_marks_error_span_red():
    svg = build_svg(_trace())
    assert "#fee2e2" in svg  # ERROR_FILL
    assert "#ef4444" in svg  # ERROR_COLOR


def test_build_svg_contains_names_annotation_and_duration():
    svg = build_svg(_trace())
    assert "LangGraph" in svg
    assert "这是 Agent 的一次完整执行" in svg  # annotation 在 <title>
    assert "500ms" in svg


def test_build_svg_escapes_special_characters():
    trace = _trace()
    trace["root_span"]["children"][0]["name"] = 'a<b&"c'
    svg = build_svg(trace)
    assert "a&lt;b&amp;" in svg
    assert 'a<b&"' not in svg


def test_render_trace_shows_graph_and_span_selector():
    pytest = __import__("pytest")
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    code = (
        "import streamlit as st\n"
        "from agenteval.web.trace_view import render_trace\n"
        f"render_trace({_trace()!r})\n"
    )
    at = AppTest.from_string(code, default_timeout=20).run()
    assert not at.exception
    assert at.subheader[0].value.startswith("Trace 详情")
    assert len(at.get("iframe")) == 1
    assert len(at.expander) == 2
