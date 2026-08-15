"""Web trace 对比页：确定性 diff（复用 diagnose.compare_traces 引擎）。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from agenteval.diagnose.tools import compare_traces
from agenteval.web.metrics import format_duration_ms

_FIELD_LABELS = {
    "error": "错误",
    "duration_ms": "耗时(ms)",
    "structure": "结构",
    "annotation": "注释",
    "exists_only_in_a": "仅 A 有",
    "exists_only_in_b": "仅 B 有",
}


def render(traces: list[dict[str, Any]], db_path: str) -> None:
    """渲染 trace 对比页：两个 trace 并排选择 + 差异表格。"""
    st.subheader("Trace 对比")
    if len(traces) < 2:
        st.info("至少需要两条 trace 才能对比，先运行两个 Agent 试试。")
        return

    by_id = {t["id"]: t for t in traces}
    ids = list(by_id)
    c1, c2 = st.columns(2)
    id_a = c1.selectbox(
        "trace A", ids, format_func=lambda i: _label(by_id[i]), key="diff_a"
    )
    others = [i for i in ids if i != id_a]
    id_b = c2.selectbox(
        "trace B", others, format_func=lambda i: _label(by_id[i]), key="diff_b"
    )

    result = compare_traces(db_path, id_a, id_b)
    if result is None:
        st.warning("对比失败：trace 不存在。")
        return

    meta_a, meta_b = result["trace_a"], result["trace_b"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("A 状态", meta_a["status"])
    m2.metric("B 状态", meta_b["status"])
    m3.metric("A 耗时", format_duration_ms(meta_a["duration_ms"]))
    m4.metric("B 耗时", format_duration_ms(meta_b["duration_ms"]))

    st.markdown(result["summary"])
    if result["differences"]:
        rows = []
        for diff in result["differences"]:
            rows.append(
                {
                    "位置": diff.get("index"),
                    "A span": diff.get("span_id_a") or "—",
                    "B span": diff.get("span_id_b") or "—",
                    "差异字段": _FIELD_LABELS.get(diff.get("field"), diff.get("field")),
                    "A 值": diff.get("value_a"),
                    "B 值": diff.get("value_b"),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.success("两个 trace 没有显著差异。")


def _label(t: dict[str, Any]) -> str:
    return f"{t.get('agent_name') or '?'} · {t.get('id')}"
