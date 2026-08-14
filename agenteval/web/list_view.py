"""trace 列表页（Streamlit UI）：搜索 + 状态/Agent/时间段筛选 + 分页 + 行按钮进详情。"""

from __future__ import annotations

import math
from typing import Any

import streamlit as st

from agenteval.storage.schema import STATUS_ERROR, STATUS_SUCCESS
from agenteval.web.row_buttons import render_row_buttons

_FILTERS = {"全部": None, "成功": STATUS_SUCCESS, "失败": STATUS_ERROR}
PAGE_SIZE = 10


def render(traces: list[dict[str, Any]]) -> None:
    """渲染 trace 列表：工具栏（搜索/状态/Agent/时间段）+ 分页 + 行按钮进详情。"""
    st.subheader("Trace 列表")
    if not traces:
        st.info("暂无 trace。用 agenteval 接入 Agent 并运行后，trace 会自动入库。")
        return

    filtered = _apply_filters(traces)
    if not filtered:
        st.warning("当前筛选条件下没有 trace。")
        return

    page = _render_pagination(len(filtered))
    page_rows = filtered[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    render_row_buttons(page_rows, key_prefix="list")


def _apply_filters(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按搜索词、状态、Agent、时间段过滤。"""
    c1, c2 = st.columns([2, 1])
    with c1:
        search = st.text_input(
            "搜索（问题内容 / Agent 名称 / Trace ID）", value="", key="list_search"
        )
    with c2:
        choice = st.selectbox("状态筛选", list(_FILTERS), key="list_status")
    status_code = _FILTERS[choice]

    agents = sorted({t["agent_name"] for t in traces if t.get("agent_name")})
    selected_agents = st.multiselect("Agent 筛选", agents, default=[], key="list_agents")
    date_range = st.date_input("时间范围", value=(), key="list_date_range")

    needle = search.strip().lower()
    result = []
    for t in traces:
        if status_code is not None and t["status"] != status_code:
            continue
        if selected_agents and t["agent_name"] not in selected_agents:
            continue
        if needle:
            hay = (
                f'{t.get("agent_name") or ""} {t.get("id") or ""} '
                f'{t.get("query_preview") or ""}'
            ).lower()
            if needle not in hay:
                continue
        result.append(t)

    if date_range and len(date_range) == 2 and all(date_range):
        start_day = date_range[0].isoformat()
        end_day = date_range[1].isoformat()
        result = [
            t
            for t in result
            if start_day <= (t.get("created_at") or "")[:10] <= end_day
        ]
    return result


def _render_pagination(total: int) -> int:
    """渲染分页控件，返回当前页码（0 基）。"""
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = st.session_state.get("list_page", 0)
    page = min(page, total_pages - 1)
    c1, c2, c3 = st.columns([1, 3, 1])
    if c1.button("‹ 上一页", key="list_prev", disabled=page == 0, width="stretch"):
        page -= 1
        st.session_state["list_page"] = page
        st.rerun()
    c2.caption(f"第 {page + 1} / {total_pages} 页 · 共 {total} 条")
    if c3.button("下一页 ›", key="list_next", disabled=page >= total_pages - 1, width="stretch"):
        page += 1
        st.session_state["list_page"] = page
        st.rerun()
    return page
