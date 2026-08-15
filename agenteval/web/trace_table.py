"""trace 展示表格：每行一个“查看”按钮，不使用 st.dataframe 行选择。

列表页与仪表盘“最近 Trace”共用。st.dataframe 的 on_select="rerun" 在
rerun / 页面切换时会触发 Streamlit 1.61.x 前端 removeChild 清理竞态
（首页、列表页均复现过），每行“查看”按钮无竞态且入口直观。
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from agenteval.web.metrics import build_rows
from agenteval.web.theme import status_badge, status_emoji


def render_trace_table(rows: list[dict[str, Any]], key_prefix: str) -> None:
    """列表页 trace 表：每行一个“查看”按钮，带 ID 列。

    供 list_view 使用。每行直接提供“查看”按钮，无需先选中再点开，避免
    st.dataframe 行选择 + rerun 触发前端 removeChild 竞态。
    """
    _render_button_rows(build_rows(rows), key_prefix, show_id=True)


def render_trace_rows_with_buttons(rows: list[dict[str, Any]], key_prefix: str) -> None:
    """每行一个“查看”按钮的 trace 列表（不依赖 st.dataframe 的 on_select）。

    供仪表盘“最近 Trace”使用：st.dataframe 的 on_select="rerun" 在图表+表格
    混排的首页上会触发 Streamlit 前端 removeChild 清理竞态，改用纯按钮行
    后不再注册行选择交互，点“查看”直接跳详情。每行带对话内容预览，方便
    确认选的是哪条 trace。
    """
    _render_button_rows(build_rows(rows), key_prefix, show_id=False)


def _render_button_rows(
    display: list[dict[str, Any]], key_prefix: str, *, show_id: bool
) -> None:
    """每行一个“查看”按钮的公共渲染实现（show_id 时表格增加 ID 列）。"""
    if show_id:
        widths = [1.0, 0.8, 1.0, 0.7, 0.7, 2.5, 0.5]
        labels = ["时间", "状态", "Agent", "Token", "耗时", "对话内容", ""]
    else:
        widths = [1.1, 0.9, 1.1, 0.8, 0.8, 2.3, 0.6]
        labels = ["时间", "状态", "Agent", "Token", "耗时", "对话内容", ""]
    head = st.columns(widths)
    for col, label in zip(head, labels):
        col.caption(label)
    for row in display:
        cols = st.columns(widths)
        badge_text, _ = status_badge(row["status"])
        cells = [
            str(row["created_at"])[:19],
            f"{status_emoji(row['status'])} {badge_text}",
            row["agent_name"] or "—",
            f"{row['tokens']:,}",
            row["duration"],
            row["query"] or "—",
        ]
        if show_id:
            cells.insert(0, (row["id"] or "")[:8])
        for col, value in zip(cols, cells):
            col.write(value)
        if cols[-1].button(
            "查看",
            key=f"{key_prefix}_view_{row['id']}",
            width="stretch",
        ):
            st.session_state["selected_trace_id"] = row["id"]
            st.rerun()
