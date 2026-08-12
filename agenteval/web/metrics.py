"""列表页/仪表盘展示用的纯计算函数（不依赖 streamlit，便于单元测试）。

聚合类纯函数（total_tokens / 耗时 / span 数）已下沉到 collector.metrics，
本模块按 web 展示需要包装（格式化、行构建）。web.metrics 不被 storage 反向依赖。
"""

from __future__ import annotations

from typing import Any

from agenteval.collector.metrics import (
    aggregate_total_tokens,
    count_spans,
    extract_query_preview,
    trace_duration_ms,
    trace_duration_seconds,
)
from agenteval.storage.schema import STATUS_LABELS

__all__ = [
    "aggregate_total_tokens",
    "trace_duration_seconds",
    "trace_duration_ms",
    "count_spans",
    "extract_query_preview",
    "format_duration",
    "format_duration_ms",
    "build_rows",
]


def format_duration(seconds: float | None) -> str:
    """把秒数格式化为易读文本（<1s 用毫秒，否则保留 1 位小数）。"""
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    return f"{seconds:.1f}s"


def format_duration_ms(ms: int | None) -> str:
    """把毫秒整数格式化为易读文本（与 format_duration 同口径）。"""
    return format_duration(None if ms is None else ms / 1000)


def build_rows(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把数据库行转换为列表页展示行。

    优先用 traces 表的冗余汇总列（total_tokens / duration_ms / query_preview），
    缺省时回退到解析 trace_json 现算——兼容旧库与未迁移行。
    """
    rows = []
    for trace in traces:
        trace_json = trace.get("trace_json")
        tokens = trace.get("total_tokens")
        duration_ms = trace.get("duration_ms")
        query = trace.get("query_preview")
        if tokens is None and trace_json:
            tokens = aggregate_total_tokens(trace_json)
        if duration_ms is None and trace_json:
            duration_ms = trace_duration_ms(trace_json)
        if query is None and trace_json:
            query = extract_query_preview(trace_json)
        rows.append(
            {
                "id": trace.get("id"),
                "created_at": trace.get("created_at"),
                "status": STATUS_LABELS.get(trace.get("status"), "unknown"),
                "agent_name": trace.get("agent_name"),
                "tokens": int(tokens or 0),
                "duration": format_duration_ms(duration_ms),
                "experiment_id": trace.get("experiment_id") or "",
                "query": query or "",
            }
        )
    return rows
