"""安全 replay 执行引擎。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from .policy import RECORDED, REPLAYABLE

_MESSAGE_TYPES = {
    "human": HumanMessage,
    "ai": AIMessage,
    "system": SystemMessage,
    "tool": ToolMessage,
}


class NotReplayableError(Exception):
    """span 类型不支持 replay 时抛出。"""


def replay_span(
    span: dict[str, Any],
    new_input: dict[str, Any] | None,
    llm_factory: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """执行安全 replay，返回对比结果。

    - llm_call：用 metadata.model_name 调 llm_factory 重建实例，真实重跑；
      未传 new_input 时沿用原 input。
    - tool_call：返回原 output 并标记 recorded_response（绝不真实执行）。
    - 其他类型：抛 NotReplayableError。

    LLM 调用失败（如 API 超时）不抛出，而是放进返回值的 error 字段。
    """
    original_output = span.get("output")
    span_type = span.get("type", "")

    if span_type in RECORDED:
        return {
            "original_output": original_output,
            "replayed_output": original_output,
            "is_recorded": True,
            "error": None,
        }

    if span_type not in REPLAYABLE:
        raise NotReplayableError(f"span 类型 {span_type} 不支持 replay")

    if llm_factory is None:
        return {
            "original_output": original_output,
            "replayed_output": None,
            "is_recorded": False,
            "error": "未配置 llm_factory，请先调用 agenteval.init(llm_factory=...)",
        }

    model_name = _resolve_model_name(span)
    raw_input = new_input if new_input is not None else span.get("input")
    effective_input = _normalize_llm_input(raw_input)
    try:
        llm = llm_factory(model_name)
        replayed_output = llm.invoke(effective_input)
    except Exception as exc:  # noqa: BLE001 —— replay 失败要提示而不是崩溃
        return {
            "original_output": original_output,
            "replayed_output": None,
            "is_recorded": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "original_output": original_output,
        "replayed_output": replayed_output,
        "is_recorded": False,
        "error": None,
    }


def _normalize_llm_input(value: Any) -> Any:
    """把 {"messages": [...]} / 消息 dict 列表转成 BaseMessage 列表。

    真实 ChatModel（如 ChatOpenAI）不接受 dict 输入，需要转成消息对象。
    """
    if isinstance(value, dict) and "messages" in value:
        value = value["messages"]
    if not isinstance(value, (list, tuple)):
        return value
    messages: list[BaseMessage] = []
    for item in value:
        if isinstance(item, BaseMessage):
            messages.append(item)
            continue
        if isinstance(item, dict):
            cls = _MESSAGE_TYPES.get(item.get("type"))
            if cls is not None:
                try:
                    messages.append(cls.model_validate(item))
                    continue
                except Exception:
                    pass
            messages.append(HumanMessage(content=str(item.get("content", item))))
            continue
        messages.append(HumanMessage(content=str(item)))
    return messages


def _resolve_model_name(span: dict[str, Any]) -> str:
    """解析真实模型 id 供 llm_factory 使用。

    metadata.model_name 可能是类名（如 "ChatOpenAI"），真正的模型 id
    （如 deepseek-v4-flash）在 invocation_params.model 里，需优先取。
    """
    meta = span.get("metadata") or {}
    invocation_params = meta.get("invocation_params")
    if isinstance(invocation_params, dict):
        for key in ("model", "model_name"):
            value = invocation_params.get(key)
            if isinstance(value, str) and value:
                return value
    for key in ("model_version", "model_name"):
        value = meta.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"
