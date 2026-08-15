"""Langfuse 兼容导出：把 trace 树转成 Langfuse 导入格式（traces + observations）。

字段命名对齐 Langfuse 导入约定（id / timestamp / traceId / parentObservationId /
startTime / endTime / level / type），observation type 映射：
llm_call → GENERATION，其余 → SPAN；error span 的 level 为 ERROR。
"""

from __future__ import annotations

import json
from typing import Any

from agenteval.storage.db import get_trace as _load_trace_row

__all__ = ["to_langfuse_payload", "export_to_jsonl"]

OBSERVATION_TYPES: dict[str, str] = {
    "llm_call": "GENERATION",
    "tool_call": "SPAN",
    "node": "SPAN",
    "agent_run": "SPAN",
}


def to_langfuse_payload(trace: dict[str, Any]) -> dict[str, Any]:
    """把一条 trace dict 转成 Langfuse 导入格式（traces + observations）。"""
    root = trace.get("root_span") or {}
    observations: list[dict[str, Any]] = []
    _walk_observations(root, trace.get("trace_id"), None, observations)
    return {
        "traces": [
            {
                "id": trace.get("trace_id"),
                "timestamp": trace.get("created_at"),
                "name": trace.get("agent_name") or root.get("name"),
                "input": root.get("input"),
                "output": root.get("output"),
                "metadata": {
                    "status": trace.get("status"),
                    "framework": trace.get("framework"),
                    "span_count": len(observations),
                },
            }
        ],
        "observations": observations,
    }


def _walk_observations(
    span: dict[str, Any],
    trace_id: str | None,
    parent_id: str | None,
    acc: list[dict[str, Any]],
) -> None:
    acc.append(
        {
            "id": span.get("span_id"),
            "traceId": trace_id,
            "parentObservationId": parent_id,
            "type": OBSERVATION_TYPES.get(span.get("type"), "SPAN"),
            "name": span.get("name") or span.get("type"),
            "startTime": span.get("started_at"),
            "endTime": span.get("ended_at"),
            "input": span.get("input"),
            "output": span.get("output"),
            "level": "ERROR" if span.get("error") else "DEFAULT",
            "metadata": {
                "annotation": span.get("annotation"),
                "error": span.get("error"),
                "span_type": span.get("type"),
                **(span.get("metadata") or {}),
            },
        }
    )
    for child in span.get("children") or []:
        _walk_observations(child, trace_id, span.get("span_id"), acc)


def export_to_jsonl(db_path: str, trace_id: str, out_path: str) -> int:
    """把一条 trace 导出为 JSONL 文件（首行 trace，随后 observations），返回记录数。

    每条记录带 kind 字段（trace / observation）便于区分；trace 不存在返回 0。
    """
    row = _load_trace_row(db_path, trace_id)
    if row is None:
        return 0
    trace = json.loads(row["trace_json"])
    payload = to_langfuse_payload(trace)
    records: list[dict[str, Any]] = [
        {"kind": "trace", **payload["traces"][0]},
        *[{"kind": "observation", **obs} for obs in payload["observations"]],
    ]
    with open(out_path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return len(records)
