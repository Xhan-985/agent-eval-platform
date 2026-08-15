"""诊断 Agent 的只读工具：看全局（摘要）、看细节（span）、做对比（diff）。

工具都是纯函数（只读 SQLite + JSON 遍历），不依赖 LLM，便于单元测试。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from agenteval.storage.db import get_trace as _load_trace_row

__all__ = ["get_trace", "get_span", "compare_traces", "TOOL_SPECS", "TOOL_DISPATCH"]


def get_trace(db_path: str, trace_id: str) -> dict[str, Any] | None:
    """读取一条 trace 的摘要（span 清单，不含完整 input/output），供诊断看全局。"""
    row = _load_trace_row(db_path, trace_id)
    if row is None:
        return None
    trace = json.loads(row["trace_json"])
    root = trace.get("root_span")
    spans = _flatten_spans(root) if root else []
    return {
        "trace_id": trace.get("trace_id"),
        "agent_name": trace.get("agent_name"),
        "status": trace.get("status"),
        "created_at": trace.get("created_at"),
        "total_tokens": row.get("total_tokens") or 0,
        "duration_ms": row.get("duration_ms"),
        "span_count": row.get("span_count") or len(spans),
        "query_preview": row.get("query_preview"),
        "spans": spans,
    }


def get_span(db_path: str, trace_id: str, span_id: str) -> dict[str, Any] | None:
    """按 id 递归定位 span，返回完整详情（input/output/metadata）。"""
    row = _load_trace_row(db_path, trace_id)
    if row is None:
        return None
    trace = json.loads(row["trace_json"])
    return _find_span(trace.get("root_span") or {}, span_id)


def _flatten_spans(root: dict[str, Any]) -> list[dict[str, Any]]:
    """把嵌套 span 树展平为带 depth 的清单（DFS 先序）。"""
    spans: list[dict[str, Any]] = []

    def walk(span: dict[str, Any], depth: int) -> None:
        spans.append(
            {
                "span_id": span.get("span_id"),
                "depth": depth,
                "type": span.get("type"),
                "name": span.get("name"),
                "duration_ms": _span_duration_ms(span),
                "annotation": span.get("annotation"),
                "error": span.get("error"),
            }
        )
        for child in span.get("children") or []:
            walk(child, depth + 1)

    walk(root, 0)
    return spans


def _span_duration_ms(span: dict[str, Any]) -> int | None:
    """span 耗时（毫秒），时间戳缺失或非法时返回 None。"""
    started, ended = span.get("started_at"), span.get("ended_at")
    if not started or not ended:
        return None
    try:
        start = datetime.fromisoformat(started)
        end = datetime.fromisoformat(ended)
        return int(round((end - start).total_seconds() * 1000))
    except ValueError:
        return None


def _find_span(span: dict[str, Any], span_id: str) -> dict[str, Any] | None:
    """在 span 树中按 span_id 递归查找（DFS 先序）。"""
    if span.get("span_id") == span_id:
        return span
    for child in span.get("children") or []:
        found = _find_span(child, span_id)
        if found:
            return found
    return None


def compare_traces(
    db_path: str, trace_id_1: str, trace_id_2: str
) -> dict[str, Any] | None:
    """确定性对比两个 trace：按 DFS 位置对齐 span，标出状态/耗时/输出差异。

    返回 dict 含 trace_a / trace_b 元信息、differences 差异清单和中文 summary。
    """
    row_a = _load_trace_row(db_path, trace_id_1)
    row_b = _load_trace_row(db_path, trace_id_2)
    if row_a is None or row_b is None:
        return None
    trace_a = json.loads(row_a["trace_json"])
    trace_b = json.loads(row_b["trace_json"])
    spans_a = _flatten_spans(trace_a.get("root_span") or {})
    spans_b = _flatten_spans(trace_b.get("root_span") or {})
    meta_a = _meta(trace_a, row_a, len(spans_a))
    meta_b = _meta(trace_b, row_b, len(spans_b))
    differences = _diff_spans(spans_a, spans_b)
    return {
        "trace_a": meta_a,
        "trace_b": meta_b,
        "span_count_a": len(spans_a),
        "span_count_b": len(spans_b),
        "differences": differences,
        "summary": _summarize_diff(meta_a, meta_b, differences),
    }


def _meta(
    trace: dict[str, Any], row: dict[str, Any], span_count: int
) -> dict[str, Any]:
    return {
        "trace_id": trace.get("trace_id"),
        "agent_name": trace.get("agent_name"),
        "status": trace.get("status"),
        "created_at": trace.get("created_at"),
        "duration_ms": row.get("duration_ms"),
        "span_count": span_count,
    }


def _diff_spans(
    spans_a: list[dict[str, Any]], spans_b: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """按位置对齐两个展平 span 清单，产出差异条目（最多 20 条防刷屏）。"""
    differences: list[dict[str, Any]] = []
    common = min(len(spans_a), len(spans_b))
    for i in range(common):
        a, b = spans_a[i], spans_b[i]
        if a["type"] != b["type"] or a["name"] != b["name"]:
            differences.append(
                {
                    "index": i,
                    "span_id_a": a["span_id"],
                    "span_id_b": b["span_id"],
                    "field": "structure",
                    "value_a": f"{a['type']}/{a['name']}",
                    "value_b": f"{b['type']}/{b['name']}",
                }
            )
        if a["error"] != b["error"]:
            differences.append(
                {
                    "index": i,
                    "span_id_a": a["span_id"],
                    "span_id_b": b["span_id"],
                    "name_a": a["name"],
                    "name_b": b["name"],
                    "field": "error",
                    "value_a": a["error"],
                    "value_b": b["error"],
                }
            )
        if a["duration_ms"] != b["duration_ms"]:
            differences.append(
                {
                    "index": i,
                    "span_id_a": a["span_id"],
                    "span_id_b": b["span_id"],
                    "name_a": a["name"],
                    "name_b": b["name"],
                    "field": "duration_ms",
                    "value_a": a["duration_ms"],
                    "value_b": b["duration_ms"],
                }
            )
        if a.get("annotation") != b.get("annotation"):
            differences.append(
                {
                    "index": i,
                    "span_id_a": a["span_id"],
                    "span_id_b": b["span_id"],
                    "field": "annotation",
                    "value_a": _shorten(a.get("annotation")),
                    "value_b": _shorten(b.get("annotation")),
                }
            )
    for i in range(common, len(spans_a)):
        differences.append(
            {
                "index": i,
                "span_id_a": spans_a[i]["span_id"],
                "span_id_b": None,
                "field": "exists_only_in_a",
                "value_a": f"{spans_a[i]['type']}/{spans_a[i]['name']}",
                "value_b": None,
            }
        )
    for i in range(common, len(spans_b)):
        differences.append(
            {
                "index": i,
                "span_id_a": None,
                "span_id_b": spans_b[i]["span_id"],
                "field": "exists_only_in_b",
                "value_a": None,
                "value_b": f"{spans_b[i]['type']}/{spans_b[i]['name']}",
            }
        )
    return differences[:20]


def _summarize_diff(
    meta_a: dict[str, Any],
    meta_b: dict[str, Any],
    differences: list[dict[str, Any]],
) -> str:
    """把差异压缩成一句中文摘要，直接作为工具结果给 LLM 看。"""
    parts: list[str] = []
    if meta_a["status"] != meta_b["status"]:
        parts.append(f"状态不同：{meta_a['status']} vs {meta_b['status']}")
    if meta_a["duration_ms"] != meta_b["duration_ms"]:
        parts.append(
            f"总耗时不同：{meta_a['duration_ms']}ms vs {meta_b['duration_ms']}ms"
        )
    if meta_a["span_count"] != meta_b["span_count"]:
        parts.append(
            f"span 数不同：{meta_a['span_count']} vs {meta_b['span_count']}"
        )
    error_diffs = [d for d in differences if d["field"] == "error"]
    for diff in error_diffs[:3]:
        span_id = diff["span_id_b"] or diff["span_id_a"]
        name = diff.get("name_b") or diff.get("name_a")
        error = diff["value_b"] or diff["value_a"]
        parts.append(f"span {span_id}（{name}）出错：{_shorten(error, 80)}")
    other_count = len(differences) - len(error_diffs)
    if other_count:
        parts.append(f"另有 {other_count} 处差异（耗时/结构/注释）")
    if not parts:
        return "两个 trace 的执行轨迹基本一致，没有显著差异。"
    return "；".join(parts) + "。"


def _shorten(value: Any, limit: int = 120) -> Any:
    """字符串截断，非字符串原样返回（保持结构化数据可读）。"""
    if not isinstance(value, str):
        return value
    if len(value) <= limit:
        return value
    return value[:limit] + "…"


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_trace",
            "description": "读取一条 trace 的摘要（span 清单，不含完整 input/output），用于看全局。",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id": {"type": "string", "description": "trace 的 id"}
                },
                "required": ["trace_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_span",
            "description": "读取某个 span 的完整详情（input/output/metadata），用于定位具体步骤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id": {"type": "string", "description": "trace 的 id"},
                    "span_id": {"type": "string", "description": "span 的 id"},
                },
                "required": ["trace_id", "span_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_traces",
            "description": "对比两个 trace 的执行差异，返回结构化差异清单与中文摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id_1": {"type": "string", "description": "第一个 trace 的 id"},
                    "trace_id_2": {"type": "string", "description": "第二个 trace 的 id"},
                },
                "required": ["trace_id_1", "trace_id_2"],
            },
        },
    },
]

TOOL_DISPATCH: dict[str, Any] = {
    "get_trace": get_trace,
    "get_span": get_span,
    "compare_traces": compare_traces,
}
