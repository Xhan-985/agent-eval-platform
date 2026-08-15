"""安全 replay 面板 UI：编辑 input、执行 replay、结构化对比、历史记录。"""

from __future__ import annotations

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
        _show_output(span.get("output"))
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
        with st.spinner("replay 中…"):
            result = replay_span(span, new_input, llm_factory)
        _render_result(span, result)
        _record_history(span, result)


def _render_result(span: dict[str, Any], result: dict[str, Any]) -> None:
    if result.get("error"):
        st.error(f"replay 失败：{result['error']}")
        hint = _error_hint(result["error"])
        if hint:
            st.info(hint)
        return
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**原 output**")
        _show_output(result.get("original_output"))
    with col2:
        st.markdown("**新 output**")
        _show_output(result.get("replayed_output"))


def _show_output(value: Any) -> None:
    """结构化展示 LLM 输出（dict/list 用格式化 JSON 的 st.code，其余用 st.code）。

    不用 st.json：复杂组件在 rerun 时易触发 Streamlit 前端 removeChild 竞态。
    """
    if value is None:
        st.caption("（空）")
        return
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except TypeError:
            text = str(value)
        st.code(text, language="json")
        return
    if hasattr(value, "content"):
        st.code(str(value.content))
        return
    st.code(str(value))


def _error_hint(error: str) -> str | None:
    """把常见 replay 报错翻译成可操作提示，帮用户定位配置问题。"""
    text = error.lower()
    if "authenticationerror" in text or "invalid_api_key" in text or " 401" in text:
        return (
            "鉴权失败：API Key 与 Base URL 不匹配。DeepSeek 的 key 需把侧边栏 "
            "“API Base URL” 改为 `https://api.deepseek.com`；OpenAI 的 key 用默认 "
            "`https://api.openai.com/v1`。"
        )
    if "connectionerror" in text or "apiconnectionerror" in text or "timeout" in text:
        return (
            "连接失败：检查侧边栏 “API Base URL” 是否正确、网络是否可达。"
        )
    if "model" in text and ("not found" in text or "does not exist" in text):
        return "模型名不可用：在侧边栏 “模型名” 填一个该服务商支持的模型 id。"
    return None


def _record_history(span: dict[str, Any], result: dict[str, Any]) -> None:
    """把本次 replay 结果记入会话历史（最多 10 条）。"""
    history: list[dict[str, Any]] = st.session_state.setdefault("replay_history", [])
    history.insert(
        0,
        {
            "span": span.get("name") or span.get("type"),
            "error": result.get("error"),
            "replayed": _format_output(result.get("replayed_output")),
        },
    )
    del history[10:]
    if history:
        st.markdown("**Replay 历史**")
        for i, item in enumerate(history):
            tag = "❌" if item["error"] else "✅"
            st.caption(f"{tag} {item['span']} → {item['replayed']}")


def _format_output(value: Any) -> str:
    """把 LLM 输出（dict / AIMessage / str）格式化为单行文本（历史展示用）。"""
    if isinstance(value, dict):
        text = value.get("text") or value.get("content")
        if text:
            return str(text)
        return json.dumps(value, ensure_ascii=False, default=str)
    if hasattr(value, "content"):
        return str(value.content)
    return str(value)
