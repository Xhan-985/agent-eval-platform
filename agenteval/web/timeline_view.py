"""trace 时间线/瀑布图：横向 Gantt 展示每个 span 的起止与耗时。

trace 工具的签名视图——按 started_at/duration 排布 span、按类型着色、error 标红。
纯计算函数 build_waterfall 不依赖 streamlit/altair，便于单元测试。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from agenteval.web.theme import ERROR_COLOR, SPAN_COLORS


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def build_waterfall(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """把 trace 树展平成时间线行（相对 root 起点的秒偏移）。纯函数。

    每行：{pos, span_id, name, type, start_s, end_s, dur_s, depth, error, annotation, tokens}
    pos 为 DFS 顺序的行号（用于纵轴排序），root 在最上。缺时间戳的 span 时长记 0。
    """
    root = trace.get("root_span")
    if not root:
        return []
    root_start = _parse_dt(root.get("started_at"))
    rows: list[dict[str, Any]] = []
    _walk(root, depth=0, root_start=root_start, rows=rows)
    # pos 反转：DFS 顺序里 root=0 在最前，希望它显示在最上 → y 轴逆序用 pos
    return rows


def _walk(
    span: dict[str, Any],
    depth: int,
    root_start: datetime | None,
    rows: list[dict[str, Any]],
) -> None:
    start = _parse_dt(span.get("started_at"))
    end = _parse_dt(span.get("ended_at"))
    if root_start is not None and start is not None:
        start_s = (start - root_start).total_seconds()
    else:
        start_s = 0.0
    if start is not None and end is not None:
        dur_s = max(0.0, (end - start).total_seconds())
    else:
        dur_s = 0.0
    meta = span.get("metadata") or {}
    tokens = int((meta.get("token_usage") or {}).get("total_tokens") or 0)
    rows.append(
        {
            "pos": len(rows),
            "span_id": span.get("span_id"),
            "name": span.get("name") or span.get("type") or "unknown",
            "type": span.get("type", "unknown"),
            "start_s": round(start_s, 3),
            "end_s": round(start_s + dur_s, 3),
            "dur_s": round(dur_s, 3),
            "depth": depth,
            "error": span.get("error"),
            "annotation": span.get("annotation") or "",
            "tokens": tokens,
        }
    )
    for child in span.get("children", []):
        _walk(child, depth + 1, root_start, rows)


def render(rows: list[dict[str, Any]]) -> None:
    """渲染瀑布图。span 选择统一在详情面板的下拉完成，此处只画图。"""
    if not rows:
        st.caption("暂无时间线数据")
        return

    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        st.caption("（未安装 altair/pandas，时间线不可用）")
        return

    df = pd.DataFrame(rows)
    # 纵轴标签：缩进 + 图标 + 名称 + 耗时
    df["label"] = [
        f'{"    " * r["depth"]}{_icon(r)} {r["name"]} · {_fmt_dur(r["dur_s"])}'
        for _, r in df.iterrows()
    ]
    # y 顺序：root 在最上 → 用 pos 逆序的 ordinal
    df["y_order"] = -df["pos"]
    df["bar_color"] = df.apply(
        lambda r: ERROR_COLOR if r["error"] else SPAN_COLORS.get(r["type"], "#64748b"), axis=1
    )

    bars = alt.Chart(df).mark_bar(cornerRadiusEnd=3, height=18).encode(
        x=alt.X("start_s:Q", title="相对耗时（秒）"),
        x2="end_s:Q",
        y=alt.Y(
            "label:N",
            sort=alt.EncodingSortField(field="y_order", order="descending"),
            title=None,
            axis=alt.Axis(labelLimit=300),
        ),
        color=alt.Color("bar_color:N", scale=None, legend=None),
        tooltip=[
            alt.Tooltip("name:N", title="名称"),
            alt.Tooltip("type:N", title="类型"),
            alt.Tooltip("dur_s:Q", title="耗时(秒)", format=".3f"),
            alt.Tooltip("tokens:Q", title="Token"),
            alt.Tooltip("annotation:N", title="注释"),
        ],
    )
    st.altair_chart(bars, width="stretch")


def _icon(row: dict[str, Any]) -> str:
    if row.get("error"):
        return "❌"
    icons = {"agent_run": "🤖", "node": "📦", "llm_call": "🔵", "tool_call": "🔧"}
    return icons.get(row.get("type"), "❓")


def _fmt_dur(seconds: float) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    return f"{seconds:.1f}s"
