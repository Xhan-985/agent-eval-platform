"""trace 聚合纯函数：总 token / 总耗时 / span 数。

放在 collector 层（trace 结构属于采集层语义），供 storage 写入冗余汇总列与
web 展示复用，避免 storage 反向依赖 web。纯函数、无副作用，便于单元测试。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

QUERY_PREVIEW_MAX_CHARS = 80


def _parse_trace(trace_json: str | dict[str, Any]) -> dict[str, Any]:
    return json.loads(trace_json) if isinstance(trace_json, str) else trace_json


def extract_query_preview(trace_json: str | dict[str, Any]) -> str | None:
    """提取 trace 的首条用户输入作为可识别预览（用于列表/仪表盘区分各 trace）。

    优先 root_span.input.query；否则取 input.messages 中第一条 user 消息的文本。
    兼容 query 字符串、[role, content] 元组、BaseMessage.model_dump() dict 三种形态。
    截断到 QUERY_PREVIEW_MAX_CHARS 并加省略号。无可用输入返回 None。
    """
    trace = _parse_trace(trace_json)
    root = trace.get("root_span") or {}
    inp = root.get("input")
    if not isinstance(inp, dict):
        return None

    text = inp.get("query")
    if isinstance(text, str) and text.strip():
        return _truncate_preview(text.strip())

    messages = inp.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            content = _message_text(msg)
            if content:
                return _truncate_preview(content)
    return None


def _message_text(msg: Any) -> str | None:
    """从单条 message 提取文本，兼容 [role, content] 元组与 message dict。"""
    if isinstance(msg, (list, tuple)) and len(msg) >= 2:
        role, content = msg[0], msg[1]
        if isinstance(role, str) and role == "user" and isinstance(content, str):
            return content
        return None
    if isinstance(msg, dict):
        # BaseMessage.model_dump(): {"type": "human", "content": "..."}
        role = msg.get("type") or msg.get("role")
        if role not in ("user", "human"):
            return None
        content = msg.get("content")
        if isinstance(content, str):
            return content
        # content 可能是 list[ContentBlock]
        if isinstance(content, list):
            parts = [p.get("text") for p in content if isinstance(p, dict) and p.get("text")]
            joined = " ".join(str(p) for p in parts if p)
            return joined or None
    return None


def _truncate_preview(text: str) -> str:
    text = " ".join(text.split())  # 折叠换行/多余空白，单行展示
    if len(text) <= QUERY_PREVIEW_MAX_CHARS:
        return text
    return text[:QUERY_PREVIEW_MAX_CHARS] + "…"


def aggregate_total_tokens(trace_json: str | dict[str, Any]) -> int:
    """遍历所有 llm_call span，聚合 metadata.token_usage.total_tokens。"""
    trace = _parse_trace(trace_json)
    root = trace.get("root_span") or {}
    return _walk_tokens(root)


def _walk_tokens(span: dict[str, Any]) -> int:
    total = 0
    if span.get("type") == "llm_call":
        usage = (span.get("metadata") or {}).get("token_usage") or {}
        total += int(usage.get("total_tokens") or 0)
    for child in span.get("children", []):
        total += _walk_tokens(child)
    return total


def trace_duration_seconds(trace_json: str | dict[str, Any]) -> float | None:
    """总耗时 = root_span.ended_at - root_span.started_at。"""
    trace = _parse_trace(trace_json)
    root = trace.get("root_span") or {}
    started, ended = root.get("started_at"), root.get("ended_at")
    if not started or not ended:
        return None
    try:
        start = datetime.fromisoformat(started)
        end = datetime.fromisoformat(ended)
        return (end - start).total_seconds()
    except ValueError:
        return None


def trace_duration_ms(trace_json: str | dict[str, Any]) -> int | None:
    """总耗时（毫秒整数），供 traces 表冗余列存储。无值返回 None。"""
    seconds = trace_duration_seconds(trace_json)
    return None if seconds is None else int(round(seconds * 1000))


def count_spans(trace_json: str | dict[str, Any]) -> int:
    """统计 trace 中所有 span 数量（含 root_span）。"""
    trace = _parse_trace(trace_json)
    root = trace.get("root_span")
    return _count(root) if root is not None else 0


def _count(span: dict[str, Any]) -> int:
    total = 1
    for child in span.get("children", []):
        total += _count(child)
    return total
