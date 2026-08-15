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


def span_duration_ms(span: dict[str, Any]) -> int | None:
    """单个 span 耗时（毫秒）；时间戳缺失或非法返回 None。"""
    started, ended = span.get("started_at"), span.get("ended_at")
    if not started or not ended:
        return None
    try:
        start = datetime.fromisoformat(started)
        end = datetime.fromisoformat(ended)
        return int(round((end - start).total_seconds() * 1000))
    except ValueError:
        return None


def span_total_tokens(span: dict[str, Any]) -> int:
    """单个 llm_call span 的 token 总数；非 llm_call 返回 0。"""
    if span.get("type") != "llm_call":
        return 0
    usage = (span.get("metadata") or {}).get("token_usage") or {}
    return int(usage.get("total_tokens") or 0)


def build_span_performance(root_span: dict[str, Any] | None) -> list[dict[str, Any]]:
    """展平所有 span 并附耗时/token 归因（占比），按耗时降序。"""
    if root_span is None:
        return []
    total_tokens = _total_tokens_of(root_span)
    root_duration = span_duration_ms(root_span) or 0
    rows: list[dict[str, Any]] = []

    def walk(span: dict[str, Any], depth: int) -> None:
        duration = span_duration_ms(span)
        tokens = span_total_tokens(span)
        rows.append(
            {
                "span_id": span.get("span_id"),
                "depth": depth,
                "type": span.get("type"),
                "name": span.get("name"),
                "duration_ms": duration,
                "duration_pct": (
                    round(duration / root_duration * 100, 1)
                    if duration and root_duration
                    else 0.0
                ),
                "tokens": tokens,
                "tokens_pct": (
                    round(tokens / total_tokens * 100, 1) if total_tokens else 0.0
                ),
                "error": span.get("error"),
                "annotation": span.get("annotation"),
            }
        )
        for child in span.get("children") or []:
            walk(child, depth + 1)

    walk(root_span, 0)
    return sorted(rows, key=lambda r: (r["duration_ms"] or 0), reverse=True)


def _total_tokens_of(span: dict[str, Any]) -> int:
    total = span_total_tokens(span)
    for child in span.get("children") or []:
        total += _total_tokens_of(child)
    return total


def estimate_cost(
    trace: dict[str, Any], pricing: dict[str, dict[str, float]]
) -> float:
    """按模型单价估算整条 trace 的 token 成本（美元）。

    pricing: {model_name: {"input": 每百万 input token 价格, "output": 每百万 output token 价格}}
    模型未配置单价时按 0 计，不抛错。
    """
    root = trace.get("root_span")
    if not root:
        return 0.0
    return _walk_cost(root, pricing)


def span_cost(
    span: dict[str, Any], pricing: dict[str, dict[str, float]]
) -> float:
    """单个 llm_call span 的 token 成本（美元）；非 llm_call 或模型无单价返回 0。"""
    if span.get("type") != "llm_call":
        return 0.0
    price = pricing.get(_model_name(span.get("metadata") or {}))
    if not price:
        return 0.0
    usage = (span.get("metadata") or {}).get("token_usage") or {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    return prompt / 1_000_000 * float(price.get("input", 0)) + (
        completion / 1_000_000 * float(price.get("output", 0))
    )


def _walk_cost(
    span: dict[str, Any], pricing: dict[str, dict[str, float]]
) -> float:
    cost = span_cost(span, pricing)
    for child in span.get("children") or []:
        cost += _walk_cost(child, pricing)
    return cost


def _model_name(meta: dict[str, Any]) -> str:
    """从 span metadata 解析真实模型 id（优先 invocation_params.model）。"""
    invocation = meta.get("invocation_params")
    if isinstance(invocation, dict):
        for key in ("model", "model_name"):
            value = invocation.get(key)
            if isinstance(value, str) and value:
                return value
    for key in ("model_version", "model_name"):
        value = meta.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"
