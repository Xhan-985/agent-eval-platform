"""仪表盘首页：KPI 卡片 + 趋势图 + 状态分布 + 最近 trace。

纯计算函数 compute_dashboard / build_trend / build_status_distribution 不依赖
streamlit，便于单元测试；render 负责渲染。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import streamlit as st

from agenteval.storage.schema import STATUS_ERROR, STATUS_SUCCESS
from agenteval.web.metrics import format_duration_ms
from agenteval.web.theme import status_badge, status_emoji


def compute_dashboard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """从 list_traces 行（含冗余汇总列）算仪表盘 KPI。纯函数。"""
    total = len(rows)
    success = sum(1 for r in rows if r.get("status") == STATUS_SUCCESS)
    error = sum(1 for r in rows if r.get("status") == STATUS_ERROR)
    success_rate = round(success / total * 100, 1) if total else 0.0
    total_tokens = sum(int(r.get("total_tokens") or 0) for r in rows)
    span_total = sum(int(r.get("span_count") or 0) for r in rows)
    durations = [int(r["duration_ms"]) for r in rows if r.get("duration_ms") is not None]
    avg_duration_ms = round(sum(durations) / len(durations)) if durations else None
    return {
        "total": total,
        "success": success,
        "error": error,
        "success_rate": success_rate,
        "total_tokens": total_tokens,
        "span_total": span_total,
        "avg_duration_ms": avg_duration_ms,
    }


def build_trend(rows: list[dict[str, Any]], days: int = 14) -> list[dict[str, Any]]:
    """近 days 天每日 trace 数与 token 消耗（按 created_at 日期分组）。纯函数。"""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"traces": 0, "tokens": 0})
    for r in rows:
        created = r.get("created_at") or ""
        day = created[:10]
        if not day:
            continue
        counts[day]["traces"] += 1
        counts[day]["tokens"] += int(r.get("total_tokens") or 0)
    items = sorted(counts.items())[-days:]
    return [{"date": d, "traces": v["traces"], "tokens": v["tokens"]} for d, v in items]


def build_status_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    """状态分布计数。纯函数。"""
    dist = {"success": 0, "error": 0, "running": 0}
    for r in rows:
        code = r.get("status")
        if code == STATUS_SUCCESS:
            dist["success"] += 1
        elif code == STATUS_ERROR:
            dist["error"] += 1
        else:
            dist["running"] += 1
    return dist


def render(rows: list[dict[str, Any]]) -> None:
    """渲染仪表盘首页。"""
    st.subheader("仪表盘")

    if not rows:
        st.info("暂无 trace。用 agenteval 接入 Agent 并运行后，这里会出现统计概览。")
        return

    stats = compute_dashboard(rows)

    # KPI 卡片行
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Trace 总数", stats["total"])
    col2.metric("成功率", f'{stats["success_rate"]}%')
    col3.metric("总 Token", f'{stats["total_tokens"]:,}')
    col4.metric("平均耗时", format_duration_ms(stats["avg_duration_ms"]))
    col5.metric("错误数", stats["error"])

    st.caption(f"共 {stats['span_total']} 个 span 被采集")

    trend = build_trend(rows)
    dist = build_status_distribution(rows)

    left, right = st.columns([3, 2])

    with left:
        st.markdown("**近 14 天 Trace 趋势**")
        _render_trend_chart(trend)

    with right:
        st.markdown("**状态分布**")
        _render_status_donut(dist)

    st.markdown("**最近 Trace**")
    _render_recent_table(rows[:10])


def _render_trend_chart(trend: list[dict[str, Any]]) -> None:
    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        st.caption("（未安装 altair/pandas，趋势图不可用）")
        return
    if not trend:
        st.caption("暂无趋势数据")
        return
    df = pd.DataFrame(trend)
    bar = alt.Chart(df).mark_bar(color="#6366f1", cornerRadiusEnd=4).encode(
        x=alt.X("date:T", title="日期"),
        y=alt.Y("traces:Q", title="Trace 数"),
        tooltip=["date:T", "traces:Q", "tokens:Q"],
    )
    st.altair_chart(bar, width="stretch")


def _render_status_donut(dist: dict[str, int]) -> None:
    total = sum(dist.values())
    if total == 0:
        st.caption("暂无数据")
        return
    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        # 退化：emoji + 文案 + 数字（不依赖 unsafe_allow_html）
        for status, count in dist.items():
            if count:
                text, _ = status_badge(status)
                st.markdown(f"{status_emoji(status)} **{text}** — {count}")
        return
    df = pd.DataFrame(
        [{"status": s, "count": c} for s, c in dist.items() if c > 0]
    )
    colors = {"success": "#16a34a", "error": "#dc2626", "running": "#2563eb"}
    chart = alt.Chart(df).mark_arc(innerRadius=50).encode(
        theta=alt.Theta("count:Q", title="数量"),
        color=alt.Color(
            "status:N",
            scale=alt.Scale(domain=list(colors), range=list(colors.values())),
            legend=alt.Legend(title="状态"),
        ),
        tooltip=["status:N", "count:Q"],
    )
    st.altair_chart(chart, width="stretch")


def _render_recent_table(rows: list[dict[str, Any]]) -> None:
    from agenteval.web.list_view import _STATUS_EMOJI
    from agenteval.web.metrics import build_rows

    display = []
    for r in build_rows(rows):
        display.append(
            {
                "问题": r["query"] or "—",
                "时间": r["created_at"],
                "状态": f"{_STATUS_EMOJI.get(r['status'], '')} {r['status']}",
                "Agent": r["agent_name"],
                "Token": r["tokens"],
                "耗时": r["duration"],
            }
        )
    event = st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        key="dash_recent_table",
        column_config={"问题": st.column_config.TextColumn(width="large")},
    )
    selected = event.selection.rows
    if selected:
        st.session_state["selected_trace_id"] = rows[selected[0]]["id"]
        st.session_state["clear_table_selection"] = True
        st.rerun()
