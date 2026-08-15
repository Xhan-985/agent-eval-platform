"""Web 诊断页：AI 助教入口（选 trace + 可选对比 + 可选问题）。"""

from __future__ import annotations

from typing import Any

import streamlit as st

import agenteval
from agenteval.web.metrics import trace_select_label


def render(traces: list[dict[str, Any]], llm_factory: Any, model_default: str) -> None:
    """渲染 AI 诊断页。llm_factory 与 model_default 复用侧边栏 replay 配置。"""
    st.subheader("AI 诊断")
    if not traces:
        st.info("暂无 trace，先运行一个 Agent 再诊断。")
        return

    by_id = {t["id"]: t for t in traces}
    ids = list(by_id)
    selected_id = st.selectbox(
        "选择 trace",
        ids,
        format_func=lambda tid: trace_select_label(by_id[tid]),
        key="diag_trace",
    )
    other_ids = [""] + [i for i in ids if i != selected_id]
    trace_id2 = st.selectbox(
        "对比第二条 trace（可选）",
        other_ids,
        format_func=lambda i: (
            "（不对比）" if not i else trace_select_label(by_id[i])
        ),
        key="diag_trace2",
    )
    question = st.text_input(
        "你想问什么（可选）",
        placeholder="例如：为什么这一步报错？",
        key="diag_question",
    )

    if st.button("开始诊断", type="primary", key="diag_run"):
        if llm_factory is None:
            st.warning("请先在侧边栏配置 API Key 后使用 AI 诊断。")
            return
        with st.spinner("诊断中，通常需要几次工具调用…"):
            report = agenteval.diagnose(
                selected_id,
                question=question.strip() or None,
                trace_id2=trace_id2 or None,
                llm_factory=llm_factory,
                model_name=model_default,
            )
        st.markdown(report)
        st.caption("本次诊断本身已作为一条 trace 入库（AgentEval 诊断助手）。")
