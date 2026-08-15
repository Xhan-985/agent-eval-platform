"""把采集器收集的扁平 span 事件组装成嵌套 trace JSON。"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .annotator import annotate
from .core import SpanCollector
from .types import Span, Trace, to_json_safe

logger = logging.getLogger("agenteval.serializer")


def build_trace(collector: SpanCollector) -> dict[str, Any]:
    """从采集完成的 collector 构建完整 trace JSON dict。"""
    if collector._root_run_id is None:
        raise ValueError("no trace collected: handler is empty")
    root_span = _build_span(collector, collector._root_run_id)
    trace = Trace(
        trace_id=str(uuid4()),
        created_at=datetime.now(UTC).isoformat(),
        status="error" if _has_error(root_span) else "success",
        framework=getattr(collector, "framework", "langgraph"),
        agent_name=collector.agent_name or root_span["name"],
        root_span=root_span,
    )
    return dict(trace)


def serialize_to_json(trace: dict[str, Any]) -> str:
    """把 trace dict 序列化为 JSON 字符串（保留中文，缩进 2）。"""
    return json.dumps(trace, ensure_ascii=False, indent=2, default=to_json_safe)


def _build_span(collector: SpanCollector, span_id: str) -> Span:
    state = collector._states[span_id]
    children_ids = sorted(
        collector._children.get(span_id, []),
        key=lambda cid: collector._states[cid]["started_at"],
    )
    span = Span(
        span_id=state["span_id"],
        type=state["type"],
        name=state["name"],
        input=state["input"],
        output=state["output"],
        error=state["error"],
        annotation=annotate(dict(state)),
        started_at=state["started_at"],
        ended_at=state["ended_at"],
        metadata=state["metadata"],
        children=[_build_span(collector, cid) for cid in children_ids],
    )
    return span


def _has_error(span: Span) -> bool:
    if span["error"]:
        return True
    return any(_has_error(child) for child in span["children"])
