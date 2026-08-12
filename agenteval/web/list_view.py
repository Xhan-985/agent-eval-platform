"""trace 列表页（Streamlit UI）：状态筛选 + 表格 + 完整 JSON 查看。"""

from __future__ import annotations

import json
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

    st.markdown("### 查看完整 trace JSON")
    selected_id = st.selectbox("选择 trace_id", [row["id"] for row in rows])
    selected = next((t for t in filtered if t["id"] == selected_id), None)
    if selected is not None:
        payload = selected["trace_json"]
        data = json.loads(payload) if isinstance(payload, str) else payload
        with st.expander("trace_json", expanded=True):
            st.json(data)
