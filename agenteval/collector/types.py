"""共享数据模型与序列化辅助工具。

span/trace 数据结构被 callback、serializer、annotator、storage、web 各层共用，
统一放在本模块，避免各层重复定义。

span type 命名与 OpenTelemetry GenAI 语义约定对齐（agent_run / node / llm_call /
tool_call），为后续 OTLP 导出保留兼容空间。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage

MAX_FIELD_BYTES = 10_000
MAX_MESSAGES = 20
MAX_ERROR_CHARS = 2_000
SUMMARY_MAX_CHARS = 50
TRUNCATED_SUFFIX = "...[truncated]"


class SpanState(TypedDict):
    """callback 内部维护的 span 上下文（扁平结构）。"""

    span_id: str
    parent_id: str | None
    type: str
    name: str
    input: Any
    output: Any
    error: str | None
    started_at: str
    ended_at: str | None
    metadata: dict[str, Any]


class Span(TypedDict):
    """trace 树中的嵌套 span。"""

    span_id: str
    type: str
    name: str
    input: Any
    output: Any
    error: str | None
    annotation: str
    started_at: str
    ended_at: str | None
    metadata: dict[str, Any]
    children: list[Span]


class Trace(TypedDict):
    """最终输出的 trace JSON。"""

    trace_id: str
    created_at: str
    status: str
    framework: str
    agent_name: str
    root_span: Span


def to_json_safe(value: Any) -> Any:
    """把任意值递归转成可 JSON 序列化的结构。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseMessage):
        return value.model_dump()
    if isinstance(value, dict):
        return {to_json_safe(k): to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def truncate_field(value: Any, max_bytes: int = MAX_FIELD_BYTES) -> Any:
    """字段序列化后超过 max_bytes 时截断为字符串并加标记。"""
    text = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), default=to_json_safe
    )
    if len(text.encode("utf-8")) <= max_bytes:
        return value
    data = text.encode("utf-8")[:max_bytes]
    return data.decode("utf-8", errors="ignore") + TRUNCATED_SUFFIX


def cap_messages(messages: list[Any], max_total: int = MAX_MESSAGES) -> list[Any]:
    """messages 超过 max_total 时保留前 10 后 10，中间加省略标记。"""
    if len(messages) <= max_total:
        return messages
    keep = max_total // 2
    omitted_count = len(messages) - 2 * keep
    marker = {"omitted": f"...[{omitted_count} messages omitted]"}
    return messages[:keep] + [marker] + messages[-keep:]
