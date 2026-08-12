"""Streamlit 主入口：streamlit run agenteval/web/app.py（或 web/app.py）。"""

from __future__ import annotations

import os

import streamlit as st

from agenteval.storage.db import get_trace, init_db, list_traces
from agenteval.web.list_view import render
from agenteval.web.trace_view import render_trace


def main() -> None:
    st.set_page_config(page_title="AgentEval", layout="wide")
    st.title("AgentEval — Agent 执行调试器")
    db_path = st.sidebar.text_input(
        "数据库路径", value=os.environ.get("AGENTEVAL_DB", "agenteval.db")
    )
    init_db(db_path)

    st.session_state.setdefault("selected_trace_id", None)
    selected_id = st.session_state.get("selected_trace_id")
    if selected_id is not None:
        if st.button("← 返回列表"):
            st.session_state["selected_trace_id"] = None
            st.rerun()
        trace = get_trace(db_path, selected_id)
        if trace is not None:
            render_trace(trace["trace_json"], trace_id=trace["id"])
        else:
            st.warning(f"trace 不存在：{selected_id}")
            st.session_state["selected_trace_id"] = None
    else:
        render(list_traces(db_path))


if __name__ == "__main__":
    main()
