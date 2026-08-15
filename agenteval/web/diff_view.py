"""Web trace 对比页：确定性 diff（复用 diagnose.compare_traces 引擎）。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from agenteval.diagnose.tools import compare_traces
from agenteval.storage.schema import STATUS_CN, display_span_name
from agenteval.web.metrics import format_duration_ms, trace_select_label
from agenteval.web.theme import type_label

_FIELD_LABELS = {
    "error": "错误",
    "duration_ms": "耗时",
    "structure": "结构",
    "annotation": "注释",
    "exists_only_in_a": "仅 A 有",
    "exists_only_in_b": "仅 B 有",
}


def render(traces: list[dict[str, Any]], db_path: str) -> None:
    """渲染 trace 对比页：两个 trace 并排选择 + 差异表格。"""
    st.subheader("Trace 对比")
    st.caption(
        "对比同一条 Agent 的两次执行（例如一次成功、一次失败），"
        "找出差异步骤——适合排查“以前能跑、现在不能”的问题。"
    )
    if len(traces) < 2:
        st.info("至少需要两条 trace 才能对比，先运行两个 Agent 试试。")
        return

    by_id = {t["id"]: t for t in traces}
    ids = list(by_id)
    c1, c2 = st.columns(2)
    id_a = c1.selectbox(
        "trace A",
        ids,
        format_func=lambda i: trace_select_label(by_id[i]),
        key="diff_a",
    )
    others = [i for i in ids if i != id_a]
    id_b = c2.selectbox(
        "trace B",
        others,
        format_func=lambda i: trace_select_label(by_id[i]),
        key="diff_b",
    )

    result = compare_traces(db_path, id_a, id_b)
    if result is None:
        st.warning("对比失败：trace 不存在。")
        return

    meta_a, meta_b = result["trace_a"], result["trace_b"]
    row_a, row_b = by_id[id_a], by_id[id_b]
    if (
        row_a.get("agent_name") != row_b.get("agent_name")
        or (row_a.get("query_preview") or "") != (row_b.get("query_preview") or "")
    ):
        st.warning(
            "这两个 trace 来自不同的 Agent 或不同的问题，逐位对比意义有限。"
            "建议选择同一 Agent、同一问题的两次执行（如一次成功一次失败），"
            "才能看出差异步骤。"
        )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("A 状态", STATUS_CN.get(meta_a["status"], meta_a["status"]))
    m2.metric("B 状态", STATUS_CN.get(meta_b["status"], meta_b["status"]))
    m3.metric("A 耗时", format_duration_ms(meta_a["duration_ms"]))
    m4.metric("B 耗时", format_duration_ms(meta_b["duration_ms"]))

    st.markdown(result["summary"])
    if result["differences"]:
        rows = []
        for diff in result["differences"]:
            rows.append(
                {
                    "位置": diff.get("index"),
                    "A span": _span_label(diff.get("type_a"), diff.get("name_a")),
                    "B span": _span_label(diff.get("type_b"), diff.get("name_b")),
                    "差异字段": _FIELD_LABELS.get(diff.get("field"), diff.get("field")),
                    "A 值": _display_value(diff.get("field"), diff.get("value_a")),
                    "B 值": _display_value(diff.get("field"), diff.get("value_b")),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.success("两个 trace 没有显著差异。")


def _span_label(span_type: Any, name: Any) -> str:
    """span 列可读标签：类型 · 名称（不带 ID）。"""
    label = type_label(span_type or "unknown")
    display_name = display_span_name(name)
    if display_name and display_name != str(span_type):
        return f"{label} · {display_name}"
    return label


def _cell(value: Any, limit: int = 80) -> Any:
    """表格单元格超长截断，保持可读。"""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def _display_value(field: Any, value: Any) -> Any:
    """按差异字段格式化值：耗时转可读文本，其余截断。"""
    if field == "duration_ms" and value is not None:
        return format_duration_ms(int(value))
    return _cell(value)
