"""列表页展示用的纯计算函数（不依赖 streamlit，便于单元测试）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from agenteval.storage.schema import STATUS_LABELS


def _parse_trace(trace_json: str | dict[str, Any]) -> dict[str, Any]:
    return json.loads(trace_json) if isinstance(trace_json, str) else trace_json


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


def format_duration(seconds: float | None) -> str:
    """把秒数格式化为易读文本（<1s 用毫秒，否则保留 1 位小数）。"""
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    return f"{seconds:.1f}s"


def build_rows(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把数据库行转换为列表页展示行。"""
    rows = []
    for trace in traces:
        trace_json = trace.get("trace_json")
        rows.append(
            {
                "id": trace.get("id"),
                "created_at": trace.get("created_at"),
                "status": STATUS_LABELS.get(trace.get("status"), "unknown"),
                "agent_name": trace.get("agent_name"),
                "tokens": aggregate_total_tokens(trace_json) if trace_json else 0,
                "duration": (
                    format_duration(trace_duration_seconds(trace_json))
                    if trace_json
                    else "-"
                ),
                "experiment_id": trace.get("experiment_id") or "",
            }
        )
    return rows
