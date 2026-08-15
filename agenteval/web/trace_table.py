"""trace 展示表格：数据表 + 行选中 + 显式"查看详情"按钮。

列表页与仪表盘"最近 Trace"共用，保证交互一致。表格负责好看，主色按钮
负责明确的操作入口（解决"只能勾选框、不知道如何进详情"的问题）。
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from agenteval.web.metrics import build_rows
from agenteval.web.theme import status_badge, status_emoji


def render_trace_table(rows: list[dict[str, Any]], key_prefix: str) -> None:
    """渲染 trace 数据表 + 选中后点击查看详情。"""
    display = []
    for row in build_rows(rows):
        badge_text, _ = status_badge(row["status"])
        display.append(
            {
                "ID": row["id"][:8],
                "时间": str(row["created_at"])[:19],
                "状态": f"{status_emoji(row['status'])} {badge_text}",
                "Agent": row["agent_name"],
                "Token": row["tokens"],
                "耗时": row["duration"],
                "问题": row["query"] or "—",
            }
        )
    event = st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"{key_prefix}_table",
        column_config={
            "问题": st.column_config.TextColumn(width="large"),
            "ID": st.column_config.TextColumn(width="small"),
        },
    )
    selected = event.selection.rows
    st.caption("点击行首 ☐ 选中一条，再点下方按钮进入详情。")
    if st.button(
        "查看选中 Trace 详情",
        type="primary",
        key=f"{key_prefix}_open",
        disabled=not selected,
        width="stretch",
    ):
        if selected:
            st.session_state["selected_trace_id"] = rows[selected[0]]["id"]
            st.rerun()


def render_trace_rows_with_buttons(rows: list[dict[str, Any]], key_prefix: str) -> None:
    """每行一个“查看”按钮的 trace 列表（不依赖 st.dataframe 的 on_select）。

    供仪表盘“最近 Trace”使用：st.dataframe 的 on_select="rerun" 在图表+表格
    混排的首页上会触发 Streamlit 前端 removeChild 清理竞态，改用纯按钮行
    后不再注册行选择交互，点“查看”直接跳详情。每行带对话内容预览，方便
    确认选的是哪条 trace。
    """
    display = build_rows(rows)
    head = st.columns([1.1, 0.9, 1.1, 0.8, 0.8, 2.3, 0.6])
    for col, label in zip(
        head, ["时间", "状态", "Agent", "Token", "耗时", "对话内容", ""]
    ):
        col.caption(label)
    for row in display:
        cols = st.columns([1.1, 0.9, 1.1, 0.8, 0.8, 2.3, 0.6])
        badge_text, _ = status_badge(row["status"])
        cols[0].write(str(row["created_at"])[:19])
        cols[1].write(f"{status_emoji(row['status'])} {badge_text}")
        cols[2].write(row["agent_name"] or "—")
        cols[3].write(f"{row['tokens']:,}")
        cols[4].write(row["duration"])
        cols[5].write(row["query"] or "—")
        if cols[6].button(
            "查看",
            key=f"{key_prefix}_view_{row['id']}",
            width="stretch",
        ):
            st.session_state["selected_trace_id"] = row["id"]
            st.rerun()
