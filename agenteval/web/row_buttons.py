"""可点击的 trace 行按钮：每行渲染为一个全宽按钮，点击进入详情。

列表页与仪表盘"最近 Trace"共用，保证交互一致（整行即按钮，无需勾选）。
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from agenteval.web.metrics import build_rows
from agenteval.web.theme import status_badge, status_emoji


def render_row_buttons(rows: list[dict[str, Any]], key_prefix: str) -> None:
    """把 trace 行渲染为全宽按钮；点击后进入详情页。"""
    for row in build_rows(rows):
        badge_text, _ = status_badge(row["status"])
        summary = (
            f"🆔 {row['id'][:8]} · {str(row['created_at'])[:19]} · "
            f"{status_emoji(row['status'])} {badge_text} · "
            f"{row['agent_name']} · {row['tokens']} tokens · {row['duration']}"
        )
        if row["query"]:
            summary += f" · {row['query'][:40]}"
        if st.button(summary, key=f"{key_prefix}-row-{row['id']}", width="stretch"):
            st.session_state["selected_trace_id"] = row["id"]
            st.rerun()
