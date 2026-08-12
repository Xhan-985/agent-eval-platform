"""trace 详情页：graphviz 树状图 + span input/output 折叠查看。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

import agenteval
from agenteval.web.metrics import format_duration
from agenteval.web.replay_view import render_replay

ICONS = {
    "agent_run": "🤖",
    "node": "📦",
    "llm_call": "🔵",
    "tool_call": "🔧",
}
ANNOTATION_MAX_CHARS = 60
ERROR_FILL = "#fca5a5"


def build_dot(trace: dict[str, Any]) -> str:
    """把 trace JSON 转成 graphviz DOT 字符串（纯函数，便于测试）。"""
    lines = [
        "digraph trace {",
        '  rankdir="TB";',
        "  graph [nodesep=0.25, ranksep=0.35];",
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];',
    ]
    root = trace.get("root_span")
    if root is not None:
        _emit_node(lines, root, parent_id=None)
    lines.append("}")
    return "\n".join(lines)


def flatten_spans(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """深度优先展平所有 span，供详情选择器使用。"""
    result: list[dict[str, Any]] = []
    root = trace.get("root_span")
    if root is not None:
        _walk(root, result)
    return result


def render_trace(
    trace_json: str | dict[str, Any], trace_id: str | None = None
) -> None:
    """详情页 UI：graphviz 图 + span 选择 + input/output 折叠。"""
    trace = json.loads(trace_json) if isinstance(trace_json, str) else trace_json
    title = f"Trace 详情：{trace_id[:8]}…" if trace_id else "Trace 详情"
    st.subheader(title)

    st.graphviz_chart(build_dot(trace))

    spans = flatten_spans(trace)
    st.markdown("### Span 详情")
    options = {_span_label(span): span for span in spans}
    selected_label = st.selectbox("选择 span", list(options))
    span = options[selected_label]
    with st.expander("input", expanded=True):
        st.json(span.get("input"))
    with st.expander("output", expanded=True):
        st.json(span.get("output"))

    render_replay(span, agenteval._llm_factory)


def _emit_node(lines: list[str], span: dict[str, Any], parent_id: str | None) -> None:
    node_id = _dot_quote(span.get("span_id") or "unknown")
    lines.append(f"  {node_id} [{_node_attrs(span)}];")
    if parent_id is not None:
        lines.append(f"  {_dot_quote(parent_id)} -> {node_id};")
    for child in span.get("children", []):
        _emit_node(lines, child, parent_id=span.get("span_id"))


def _node_attrs(span: dict[str, Any]) -> str:
    span_type = span.get("type", "unknown")
    icon = "❌" if span.get("error") else ICONS.get(span_type, "❓")
    name = _dot_escape(str(span.get("name") or span_type))
    annotation = _dot_escape(
        _truncate(str(span.get("annotation") or ""), ANNOTATION_MAX_CHARS)
    )
    duration = format_duration(_span_duration_seconds(span))
    label = "\\n".join([f"{icon} {name}", annotation, duration])
    attrs = [f'label="{label}"']
    if span.get("error"):
        attrs.append(f'fillcolor="{ERROR_FILL}"')
    return ", ".join(attrs)


def _span_label(span: dict[str, Any]) -> str:
    span_type = span.get("type", "unknown")
    icon = "❌" if span.get("error") else ICONS.get(span_type, "❓")
    name = span.get("name") or span_type
    duration = format_duration(_span_duration_seconds(span))
    return f"{icon} {name} · {duration} · {span.get('span_id', '')}"


def _span_duration_seconds(span: dict[str, Any]) -> float | None:
    started, ended = span.get("started_at"), span.get("ended_at")
    if not started or not ended:
        return None
    try:
        start = datetime.fromisoformat(started)
        end = datetime.fromisoformat(ended)
        return (end - start).total_seconds()
    except ValueError:
        return None


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _dot_escape(text: str) -> str:
    """DOT 字符串转义：反斜杠、双引号、换行。"""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _dot_quote(text: str) -> str:
    return f'"{_dot_escape(text)}"'


def _walk(span: dict[str, Any], acc: list[dict[str, Any]]) -> None:
    acc.append(span)
    for child in span.get("children", []):
        _walk(child, acc)
