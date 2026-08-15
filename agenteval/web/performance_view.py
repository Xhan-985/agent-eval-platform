"""trace 详情页"性能"tab：span 耗时/token 归因排行。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from agenteval.collector.metrics import build_span_performance, span_cost
from agenteval.storage.schema import display_span_name
from agenteval.web.metrics import format_duration_ms
from agenteval.web.theme import type_label

# 成本估算默认单价（每百万 token，美元），仅供教学参考，不保证与实时价格一致。
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {"input": 0.5, "output": 1.0},
    "deepseek-v4-pro": {"input": 2.0, "output": 6.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4o": {"input": 2.5, "output": 10.0},
}


def render(trace: dict[str, Any]) -> None:
    """渲染性能排行表：按耗时降序 + token 归因 + 可选成本估算。"""
    rows = build_span_performance(trace.get("root_span"))
    if not rows:
        st.caption("暂无 span 数据")
        return

    spans_by_id = {
        span["span_id"]: span
        for span in _collect_spans(trace.get("root_span") or {})
    }
    show_cost = st.checkbox(
        "显示成本估算（按常见模型单价）", value=False, key="perf_show_cost"
    )

    table = []
    for row in rows:
        entry = {
            "步骤": display_span_name(row["name"]) or row["type"],
            "类型": type_label(row["type"]),
            "耗时": format_duration_ms(row["duration_ms"]),
            "耗时占比": f'{row["duration_pct"]:.1f}%',
            "Token": row["tokens"] or "",
            "Token 占比": f'{row["tokens_pct"]:.1f}%' if row["tokens_pct"] else "",
            "错误": "⚠️" if row["error"] else "",
        }
        if show_cost:
            span = spans_by_id.get(row["span_id"]) or {}
            entry["成本(美元)"] = f"{span_cost(span, DEFAULT_PRICING):.4f}"
        table.append(entry)

    st.dataframe(table, width="stretch", hide_index=True)
    slowest = rows[0]
    root_id = (trace.get("root_span") or {}).get("span_id")
    if slowest["span_id"] != root_id:
        st.caption(
            f"⏱ 最慢步骤：{display_span_name(slowest['name'])} · "
            f"{format_duration_ms(slowest['duration_ms'])}"
            f"（耗时占比 {slowest['duration_pct']:.1f}%）"
        )


def _collect_spans(span: dict[str, Any]) -> list[dict[str, Any]]:
    acc = [span]
    for child in span.get("children") or []:
        acc.extend(_collect_spans(child))
    return acc
