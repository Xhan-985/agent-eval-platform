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
