"""trace 列表页（Streamlit UI）：状态筛选 + 表格 + 进入详情导航。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from agenteval.storage.schema import STATUS_ERROR, STATUS_SUCCESS
from agenteval.web.metrics import build_rows

_STATUS_EMOJI = {"success": "✅", "error": "❌", "running": "⏳", "unknown": "❓"}
_FILTERS = {"全部": None, "成功": STATUS_SUCCESS, "失败": STATUS_ERROR}


def render(traces: list[dict[str, Any]]) -> None:
    """渲染 trace 列表：筛选下拉框 + 数据表 + 选中 trace 的完整 JSON。"""
    st.subheader("Trace 列表")
    if not traces:
        st.info("暂无 trace。用 agenteval 接入 Agent 并运行后，trace 会自动入库。")
        return

    choice = st.selectbox("状态筛选", list(_FILTERS))
    status_code = _FILTERS[choice]
    filtered = [
        t for t in traces if status_code is None or t["status"] == status_code
    ]
    if not filtered:
        st.warning("当前筛选条件下没有 trace。")
        return

    rows = build_rows(filtered)
    display_rows = [
        {**row, "status": f"{_STATUS_EMOJI.get(row['status'], '')} {row['status']}"}
        for row in rows
    ]
    st.dataframe(display_rows, width="stretch", hide_index=True)

    st.markdown("### 进入详情")
    for row in rows:
        summary = (
            f"{row['created_at']} ｜ {row['agent_name']} ｜ {row['status']} ｜ "
            f"{row['tokens']} tokens ｜ {row['duration']}"
            + (f" ｜ {row['experiment_id']}" if row["experiment_id"] else "")
        )
        col1, col2 = st.columns([4, 1])
        col1.caption(summary)
        if col2.button("查看详情", key=f"view-{row['id']}"):
            st.session_state["selected_trace_id"] = row["id"]
            st.rerun()
