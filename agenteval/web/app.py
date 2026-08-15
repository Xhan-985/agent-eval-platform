"""Streamlit 主入口：streamlit run agenteval/web/app.py（或 web/app.py）。"""

from __future__ import annotations

import os

import streamlit as st

import agenteval
from agenteval.storage.db import get_trace, init_db, list_traces
from agenteval.web.dashboard_view import render as render_dashboard
from agenteval.web.diagnose_view import render as render_diagnose
from agenteval.web.diff_view import render as render_diff
from agenteval.web.list_view import render as render_list
from agenteval.web.trace_view import render_trace

MODEL_OPTIONS = {
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o": "gpt-4o",
    "qwen2.5:7b（本地 Ollama）": "qwen2.5:7b",
    "自定义…": "__custom__",
}


def main() -> None:
    st.set_page_config(
        page_title="AgentEval",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.title("AgentEval — Agent 执行调试器")

    db_path = st.sidebar.text_input(
        "数据库路径", value=os.environ.get("AGENTEVAL_DB", "agenteval.db")
    )

    # DB 路径校验：父目录不存在或不可写时给友好提示，不让异常冒泡到页面顶。
    db_ok = True
    try:
        init_db(db_path)
    except Exception as exc:  # noqa: BLE001 —— UI 层要把存储异常转成可读提示
        db_ok = False
        st.sidebar.error(f"数据库初始化失败：{exc}")

    # Replay LLM 配置（侧边栏）
    st.sidebar.markdown("### Replay LLM")
    model_choice = st.sidebar.selectbox(
        "模型名", list(MODEL_OPTIONS), key="llm_model"
    )
    if MODEL_OPTIONS[model_choice] == "__custom__":
        model_default = st.sidebar.text_input(
            "自定义模型名", value="", key="llm_model_custom"
        )
    else:
        model_default = MODEL_OPTIONS[model_choice]
    base_url = st.sidebar.text_input(
        "API Base URL",
        value="https://api.openai.com/v1",
        help="OpenAI 默认；DeepSeek 用 https://api.deepseek.com",
    )
    api_key = st.sidebar.text_input(
        "API Key", type="password", value=os.environ.get("OPENAI_API_KEY", "")
    )

    llm_factory = None
    if api_key:
        fake_names = {"FakeListChatModel", "unknown", "llm", ""}

        def _factory(name: str):
            from langchain_openai import ChatOpenAI

            effective = name if name and name not in fake_names else model_default
            return ChatOpenAI(
                model=effective,
                api_key=api_key,
                base_url=base_url,
            )

        llm_factory = _factory
        # 保留模块级注册：SDK 的 last_trace replay 路径与示例代码仍读 agenteval._llm_factory。
        agenteval.init(db_path=db_path, llm_factory=_factory)
    else:
        st.sidebar.info("配置 API Key 后可使用 replay 功能")

    if not db_ok:
        st.warning("数据库不可用，请检查侧边栏的数据库路径。")
        return

    # 导航：仪表盘 / Trace 列表；选中 trace 时进入详情页。
    st.session_state.setdefault("selected_trace_id", None)
    # 详情页"用 AI 诊断"按钮跳转：widget 实例化前先写 nav，避免 SessionState 报错。
    if st.session_state.pop("diag_jump", False):
        st.session_state["nav"] = "AI 诊断"
    nav = st.sidebar.radio(
        "导航",
        ["仪表盘", "Trace 列表", "AI 诊断", "Trace 对比"],
        key="nav",
        horizontal=True,
    )

    selected_id = st.session_state.get("selected_trace_id")
    if selected_id is not None:
        if st.button("← 返回列表", type="primary"):
            st.session_state["selected_trace_id"] = None
            st.session_state["clear_table_selection"] = True
            st.rerun()
        if st.button("用 AI 诊断这条 trace", key="diag_from_detail"):
            st.session_state["diag_trace"] = selected_id
            st.session_state["diag_jump"] = True
            st.session_state["selected_trace_id"] = None
            st.rerun()
        trace = get_trace(db_path, selected_id)
        if trace is not None:
            render_trace(
                trace["trace_json"],
                trace_id=trace["id"],
                llm_factory=llm_factory,
                trace_meta=trace,
            )
        else:
            st.warning(f"trace 不存在：{selected_id}")
            st.session_state["selected_trace_id"] = None
    elif nav == "Trace 列表":
        render_list(list_traces(db_path))
    elif nav == "AI 诊断":
        render_diagnose(list_traces(db_path), llm_factory, model_default)
    elif nav == "Trace 对比":
        render_diff(list_traces(db_path), db_path)
    else:
        render_dashboard(list_traces(db_path))


if __name__ == "__main__":
    main()
