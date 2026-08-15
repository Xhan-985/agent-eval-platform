"""OTLP 兼容导出：把 trace 转成 OpenTelemetry OTLP/HTTP JSON 格式。

零依赖实现（不引入 opentelemetry SDK）：直接生成 OTLP/HTTP JSON 协议中的
``ExportTraceServiceRequest``，可保存为 JSON 文件，也可 POST 到任意
OTLP/HTTP 端点（如 Jaeger Collector 的 ``/v1/traces``、Grafana Tempo）。

字段映射遵循 OpenTelemetry 语义约定：

- span id / trace id：agenteval 的字符串 id 派生为定长 hex（已是 hex 则原样）；
- 时间戳：ISO 8601 → unix 纳秒（proto3 JSON 约定 int64 用字符串）；
- llm_call 附加 ``gen_ai.*`` 属性（system / model / usage tokens）；
- error span：status.code=2 + exception event。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from agenteval.storage.db import get_trace as _load_trace_row

__all__ = ["to_otlp_payload", "export_otlp_json", "send_otlp_http"]

# OpenTelemetry SpanKind：INTERNAL=1（agent 执行属于库内部工作）
_KIND_INTERNAL = 1
# StatusCode：OK=1，ERROR=2
_STATUS_OK = 1
_STATUS_ERROR = 2

_HEX32 = re.compile(r"[0-9a-fA-F]{32}")
_HEX16 = re.compile(r"[0-9a-fA-F]{16}")


def _service_version() -> str:
    try:
        return version("agenteval-debugger")
    except PackageNotFoundError:
        return "0.0.0"


def to_otlp_payload(trace: dict[str, Any]) -> dict[str, Any]:
    """把一条 trace dict 转成 OTLP/HTTP JSON 的 ExportTraceServiceRequest。"""
    root = trace.get("root_span")
    spans: list[dict[str, Any]] = []
    if root is not None:
        _walk_spans(root, trace.get("trace_id"), None, spans)

    resource_attrs = [
        _attr("service.name", "agenteval"),
        _attr("service.version", _service_version()),
        _attr("agent.framework", trace.get("framework") or "unknown"),
    ]
    if trace.get("agent_name"):
        resource_attrs.append(_attr("agent.name", trace["agent_name"]))

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": resource_attrs,
                    "droppedAttributesCount": 0,
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "agenteval.otlp",
                            "version": _service_version(),
                        },
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def export_otlp_json(db_path: str, trace_id: str, out_path: str) -> int:
    """把一条 trace 导出为 OTLP JSON 文件，返回 span 数；trace 不存在返回 0。"""
    row = _load_trace_row(db_path, trace_id)
    if row is None:
        return 0
    trace = json.loads(row["trace_json"])
    payload = to_otlp_payload(trace)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
    return len(payload["resourceSpans"][0]["scopeSpans"][0]["spans"])


def send_otlp_http(
    db_path: str,
    trace_id: str,
    endpoint: str,
    *,
    timeout: float = 10.0,
) -> None:
    """把一条 trace POST 到 OTLP/HTTP JSON 端点（如 http://localhost:4318/v1/traces）。

    trace 不存在时抛 LookupError；网络/服务端错误向上抛，由调用方处理。
    """
    row = _load_trace_row(db_path, trace_id)
    if row is None:
        raise LookupError(f"trace 不存在：{trace_id}")
    trace = json.loads(row["trace_json"])
    payload = to_otlp_payload(trace)
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def _walk_spans(
    span: dict[str, Any],
    trace_id: str | None,
    parent_id: str | None,
    acc: list[dict[str, Any]],
) -> None:
    acc.append(_to_span(span, trace_id, parent_id))
    for child in span.get("children") or []:
        _walk_spans(child, trace_id, span.get("span_id"), acc)


def _to_span(
    span: dict[str, Any], trace_id: str | None, parent_id: str | None
) -> dict[str, Any]:
    started = _iso_to_unix_nano(span.get("started_at"))
    ended = _iso_to_unix_nano(span.get("ended_at"))
    if ended is None:
        ended = started
    if started is None:
        started = ended

    span_type = span.get("type", "unknown")
    name = span.get("name") or span_type
    attributes = [_attr("span.type", span_type)]
    if name and name != span_type:
        attributes.append(_attr("span.name", name))
    if span.get("annotation"):
        attributes.append(_attr("annotation", span["annotation"]))
    if span.get("error"):
        attributes.append(_attr("error", span["error"]))
    attributes.extend(_genai_attributes(span, span_type))

    result: dict[str, Any] = {
        "traceId": _to_trace_id(trace_id),
        "spanId": _to_span_id(span.get("span_id")),
        "name": name,
        "kind": _KIND_INTERNAL,
        "startTimeUnixNano": _nano_str(started),
        "endTimeUnixNano": _nano_str(ended),
        "attributes": attributes,
        "droppedAttributesCount": 0,
        "status": {"code": _STATUS_ERROR if span.get("error") else _STATUS_OK},
    }
    if parent_id:
        result["parentSpanId"] = _to_span_id(parent_id)
    if span.get("error"):
        result["events"] = [
            {
                "timeUnixNano": _nano_str(ended or started),
                "name": "exception",
                "attributes": [
                    _attr("exception.type", span_type),
                    _attr("exception.message", span["error"]),
                ],
                "droppedAttributesCount": 0,
            }
        ]
    return result


def _genai_attributes(span: dict[str, Any], span_type: str) -> list[dict[str, Any]]:
    """llm_call span 附加 gen_ai.* 语义属性（token 用量 / 模型名）。"""
    if span_type != "llm_call":
        return []
    meta = span.get("metadata") or {}
    attrs = [_attr("gen_ai.system", "unknown")]
    model = meta.get("model_version") or meta.get("model_name")
    if model:
        attrs.append(_attr("gen_ai.request.model", model))
    usage = meta.get("token_usage") or {}

    def _first(*keys: str) -> int | None:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                return int(value)
        return None

    input_tokens = _first("input_tokens", "prompt_tokens")
    if input_tokens is not None:
        attrs.append(_attr("gen_ai.usage.input_tokens", input_tokens))
    output_tokens = _first("output_tokens", "completion_tokens")
    if output_tokens is not None:
        attrs.append(_attr("gen_ai.usage.output_tokens", output_tokens))
    total_tokens = _first("total_tokens")
    if total_tokens is not None:
        attrs.append(_attr("gen_ai.usage.total_tokens", total_tokens))
    return attrs


def _attr(key: str, value: Any) -> dict[str, Any]:
    """构造 OTLP KeyValue（proto3 JSON：int64 用字符串表示）。"""
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, (int, float)):
        return {"key": key, "value": {"intValue": str(int(value))}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _iso_to_unix_nano(value: Any) -> int | None:
    """ISO 8601 → unix 纳秒；解析失败返回 None。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1_000_000_000)


def _nano_str(nano: int | None) -> str:
    return str(nano or 0)


def _to_trace_id(value: Any) -> str:
    text = str(value or "")
    if _HEX32.fullmatch(text):
        return text.lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _to_span_id(value: Any) -> str:
    text = str(value or "")
    if _HEX16.fullmatch(text):
        return text.lower()
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
