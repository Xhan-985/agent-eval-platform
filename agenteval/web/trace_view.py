"""trace 详情页：摘要卡 + 时间线/调用树/Span 列表 + span 详情 + replay。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

from agenteval.web import timeline_view
from agenteval.web.metrics import format_duration, format_duration_ms
from agenteval.web.replay_view import render_replay
from agenteval.web.theme import status_badge, status_emoji, type_label

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
        '  rankdir="LR";',
        "  graph [nodesep=0.25, ranksep=0.5];",
        '  edge [dir="forward", arrowhead="normal"];',
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
    trace_json: str | dict[str, Any],
    trace_id: str | None = None,
    llm_factory: Any = None,
    trace_meta: dict[str, Any] | None = None,
) -> None:
    """详情页 UI：摘要卡 + 三视图 tabs + span 详情 + replay。

    llm_factory 由 app.py 显式注入（不再读 agenteval._llm_factory 私有变量）；
    trace_meta 为 get_trace 返回的数据库行，用于摘要卡展示冗余汇总列。
    """
    trace = json.loads(trace_json) if isinstance(trace_json, str) else trace_json
    title = f"Trace 详情：{trace_id[:8]}…" if trace_id else "Trace 详情"
    st.subheader(title)

    _render_summary(trace, trace_id, trace_meta)

    spans = flatten_spans(trace)
    tab_timeline, tab_tree, tab_list = st.tabs(["时间线", "调用树", "Span 列表"])

    with tab_timeline:
        timeline_view.render(timeline_view.build_waterfall(trace))

    with tab_tree:
        st.graphviz_chart(build_dot(trace))

    with tab_list:
        _render_span_table(spans)

    _render_span_detail(spans, llm_factory)


def _render_summary(
    trace: dict[str, Any], trace_id: str | None, trace_meta: dict[str, Any] | None
) -> None:
    """顶部摘要卡：状态徽标 + Agent + 模型 + 时间 + 耗时 + Token + span 数。"""
    meta = trace_meta or {}
    status = trace.get("status", "unknown")
    badge_text, _ = status_badge(status)
    agent = trace.get("agent_name") or meta.get("agent_name") or "—"
    created = meta.get("created_at") or trace.get("created_at") or "—"

    duration_ms = meta.get("duration_ms")
    total_tokens = meta.get("total_tokens")
    span_count = meta.get("span_count")
    if duration_ms is None:
        from agenteval.collector.metrics import trace_duration_ms

        duration_ms = trace_duration_ms(trace)
    if total_tokens is None:
        from agenteval.collector.metrics import aggregate_total_tokens

        total_tokens = aggregate_total_tokens(trace)
    if span_count is None:
        from agenteval.collector.metrics import count_spans

        span_count = count_spans(trace)

    model = _extract_model(trace)
    experiment = meta.get("experiment_id")

    # 用 emoji + 原生 markdown 表达状态徽标，避免 unsafe_allow_html 触发
    # Streamlit 的 React DOM removeChild 报错（HTML 与 markdown 混排所致）。
    st.markdown(f"### {status_emoji(status)} {agent}")
    caption_bits = [f"`{created[:19]}`"]
    if model:
        caption_bits.append(f"模型 `{model}`")
    if experiment:
        caption_bits.append(f"实验 `{experiment}`")
    st.caption(" · ".join(caption_bits))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总耗时", format_duration_ms(duration_ms))
    c2.metric("总 Token", f"{int(total_tokens or 0):,}")
    c3.metric("Span 数", span_count or 0)
    c4.metric("状态", f"{status_emoji(status)} {badge_text}")


def _render_span_table(spans: list[dict[str, Any]]) -> None:
    """Span 列表 tab：平铺表。"""
    if not spans:
        st.caption("暂无 span")
        return
    rows = []
    for s in spans:
        rows.append(
            {
                "类型": type_label(s.get("type", "")),
                "名称": s.get("name") or s.get("type"),
                "耗时": format_duration(_span_duration_seconds(s)),
                "错误": "是" if s.get("error") else "",
                "注释": s.get("annotation") or "",
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)


def _render_span_detail(spans: list[dict[str, Any]], llm_factory: Any) -> None:
    """span 详情面板：下拉选 span → 全文注释 + input/output + replay。"""
    if not spans:
        return
    st.markdown("### Span 详情")
    options = {_span_label(span): span for span in spans}
    selected_label = st.selectbox("选择 span", list(options), key="span_select")
    span = options[selected_label]

    st.markdown(f"**注释**：{span.get('annotation') or '—'}")

    meta = span.get("metadata") or {}
    usage = meta.get("token_usage")
    detail_cols = st.columns([2, 1, 1])
    detail_cols[0].caption(
        f"类型：{type_label(span.get('type', ''))} · "
        f"耗时：{format_duration(_span_duration_seconds(span))}"
    )
    if usage:
        detail_cols[1].caption(
            f"Token：{usage.get('total_tokens', '—')}"
            f"（prompt {usage.get('prompt_tokens', '—')} / "
            f"completion {usage.get('completion_tokens', '—')}）"
        )
    if span.get("error"):
        detail_cols[2].caption(f"⚠️ {span['error']}")

    with st.expander("input", expanded=True):
        st.json(span.get("input"))
    with st.expander("output", expanded=True):
        st.json(span.get("output"))

    render_replay(span, llm_factory)


def _extract_model(trace: dict[str, Any]) -> str | None:
    """从首个 llm_call span 提取 model_version（best-effort）。"""
    root = trace.get("root_span")
    return _first_model(root) if root else None


def _first_model(span: dict[str, Any]) -> str | None:
    """深度优先找第一个含模型信息的 llm_call span。"""
    if span.get("type") == "llm_call":
        meta = span.get("metadata") or {}
        for key in ("model_version", "model_name"):
            val = meta.get(key)
            if isinstance(val, str) and val:
                return val
    for child in span.get("children", []):
        found = _first_model(child)
        if found:
            return found
    return None


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
