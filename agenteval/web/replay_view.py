"""安全 replay 面板 UI：编辑 input、执行 replay、对比展示。"""

from __future__ import annotations

import html
import json
from collections.abc import Callable
from typing import Any

import streamlit as st

from agenteval.replay.policy import get_replay_policy
from agenteval.replay.runner import replay_span


def render_replay(
    span: dict[str, Any], llm_factory: Callable[[str], Any] | None
) -> None:
    """渲染安全 replay 面板。"""
    st.markdown("### Replay")
    policy = get_replay_policy(span.get("type", ""))
    if policy == "not_supported":
        st.markdown("该 span 类型不支持 replay")
        return
    if policy == "recorded":
        st.warning("⚠️ 录播响应（未真实执行，避免副作用）")
        st.json(span.get("output"))
        return

    default_input = json.dumps(span.get("input"), ensure_ascii=False, indent=2)
    new_input_text = st.text_area(
        "修改后的 input（JSON）",
        value=default_input,
        height=150,
        key=f"replay-input-{span.get('span_id')}",
    )
    if st.button("replay", key=f"replay-btn-{span.get('span_id')}"):
        try:
            new_input = json.loads(new_input_text)
        except json.JSONDecodeError as exc:
            st.error(f"input JSON 解析失败：{exc}")
            return
        _render_result(replay_span(span, new_input, llm_factory))


def _render_result(result: dict[str, Any]) -> None:
    if result.get("error"):
        st.error(f"replay 失败：{result['error']}")
        return
    col1, col2 = st.columns(2)
    original = _format_output(result["original_output"])
    replayed = _format_output(result["replayed_output"])
    with col1:
        st.markdown("**原 output**")
        st.markdown(
            f"<span style='color:gray'>{html.escape(original)}</span>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown("**新 output**")
        st.markdown(
            f"<span style='color:green;font-weight:bold'>{html.escape(replayed)}</span>",
            unsafe_allow_html=True,
        )


def _format_output(value: Any) -> str:
    """把 LLM 输出（dict / AIMessage / str）格式化为文本。"""
    if isinstance(value, dict):
        text = value.get("text") or value.get("content")
        if text:
            return str(text)
        return json.dumps(value, ensure_ascii=False, default=str)
    if hasattr(value, "content"):
        return str(value.content)
    return str(value)
