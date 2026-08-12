"""trace 列表页（Streamlit UI）：搜索 + 状态/Agent 筛选 + 分页 + 行选中进详情。"""

from __future__ import annotations

import math
from typing import Any

import streamlit as st

from agenteval.storage.schema import STATUS_ERROR, STATUS_SUCCESS
from agenteval.web.metrics import build_rows

_STATUS_EMOJI = {"success": "✅", "error": "❌", "running": "⏳", "unknown": "❓"}
_FILTERS = {"全部": None, "成功": STATUS_SUCCESS, "失败": STATUS_ERROR}
PAGE_SIZE = 15


def render(traces: list[dict[str, Any]]) -> None:
    """渲染 trace 列表：工具栏（搜索/状态/Agent）+ 分页表格 + 行选中进详情。"""
    st.subheader("Trace 列表")
    if not traces:
        st.info("暂无 trace。用 agenteval 接入 Agent 并运行后，trace 会自动入库。")
        return

    # 返回列表时清掉表格选中，避免立即重新跳转详情
    if st.session_state.get("clear_table_selection"):
        st.session_state.pop("trace_table", None)
        st.session_state["clear_table_selection"] = False

    filtered = _apply_filters(traces)
    if not filtered:
        st.warning("当前筛选条件下没有 trace。")
        return

    page = _render_pagination(len(filtered))
    page_rows = filtered[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    display = _display_rows(page_rows)
    event = st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        key="trace_table",
        column_config={
            "问题": st.column_config.TextColumn(width="large"),
            "时间": st.column_config.TextColumn(width="medium"),
        },
    )
    selected = event.selection.rows
    if selected:
        idx = selected[0]
        st.session_state["selected_trace_id"] = page_rows[idx]["id"]
        st.session_state["list_page"] = page
        st.rerun()


def _apply_filters(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按搜索词、状态、Agent 过滤。"""
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


def _display_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把数据库行转成表格展示行。"""
    display = []
    for r in build_rows(rows):
        status_text = r["status"]
        display.append(
            {
                "问题": r["query"] or "—",
                "时间": r["created_at"],
                "状态": f"{_STATUS_EMOJI.get(status_text, '')} {status_text}",
                "Agent": r["agent_name"],
                "Token": r["tokens"],
                "耗时": r["duration"],
                "实验": r["experiment_id"] or "—",
            }
        )
    return display
