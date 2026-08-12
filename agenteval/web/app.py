"""Streamlit 主入口：streamlit run agenteval/web/app.py（或 web/app.py）。"""

from __future__ import annotations

import os

import streamlit as st

from agenteval.storage.db import init_db, list_traces
from agenteval.web.list_view import render


def main() -> None:
    st.set_page_config(page_title="AgentEval", layout="wide")
    st.title("AgentEval — Agent 执行调试器")
    db_path = st.sidebar.text_input(
        "数据库路径", value=os.environ.get("AGENTEVAL_DB", "agenteval.db")
    )
    init_db(db_path)
    render(list_traces(db_path))


if __name__ == "__main__":
    main()
