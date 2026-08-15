"""OTLP 导出（to_otlp_payload / export_otlp_json / send_otlp_http）的单元测试。"""

import json
from datetime import UTC, datetime

import pytest

import agenteval.export.otlp as otlp
from agenteval.export.otlp import export_otlp_json, send_otlp_http, to_otlp_payload
from agenteval.storage.db import init_db, insert_trace


def _trace(trace_id: str = "t1") -> dict:
    return {
        "trace_id": trace_id,
        "created_at": "2026-08-15T00:00:00+00:00",
        "status": "error",
        "framework": "langgraph",
        "agent_name": "ReAct Agent",
        "root_span": {
            "span_id": "s-root",
            "type": "agent_run",
            "name": "ReAct Agent",
            "input": {"query": "LangGraph 是什么？"},
            "output": {"answer": "done"},
            "error": None,
            "annotation": "这是 Agent 的一次完整执行。",
            "started_at": "2026-08-15T00:00:00+00:00",
            "ended_at": "2026-08-15T00:00:05+00:00",
            "metadata": {},
            "children": [
                {
                    "span_id": "s-llm1",
                    "type": "llm_call",
                    "name": "deepseek-v4-flash",
                    "input": {"messages": ["hi"]},
                    "output": {"text": "out"},
                    "error": None,
                    "annotation": "Agent 正在决定下一步",
                    "started_at": "2026-08-15T00:00:01+00:00",
                    "ended_at": "2026-08-15T00:00:02+00:00",
                    "metadata": {
                        "model_version": "deepseek-v4-flash",
                        "token_usage": {
                            "total_tokens": 100,
                            "prompt_tokens": 40,
                            "completion_tokens": 60,
                        },
                    },
                    "children": [],
                },
                {
                    "span_id": "s-tool",
                    "type": "tool_call",
                    "name": "search",
                    "input": {"query": "LangGraph"},
                    "output": {"text": "out"},
                    "error": "boom",
                    "annotation": "Agent 调用了搜索工具",
                    "started_at": "2026-08-15T00:00:03+00:00",
                    "ended_at": "2026-08-15T00:00:04+00:00",
                    "metadata": {},
                    "children": [],
                },
            ],
        },
    }


def _spans(payload: dict) -> list[dict]:
    return payload["resourceSpans"][0]["scopeSpans"][0]["spans"]


def _attr_map(span: dict) -> dict[str, str | int]:
    out = {}
    for item in span["attributes"]:
        value = item["value"]
        out[item["key"]] = value.get(
            "stringValue", value.get("intValue", value.get("boolValue"))
        )
    return out


def test_to_otlp_payload_structure():
    payload = to_otlp_payload(_trace())

    assert len(payload["resourceSpans"]) == 1
    resource = payload["resourceSpans"][0]["resource"]
    res_attrs = _attr_map({"attributes": resource["attributes"]})
    assert res_attrs["service.name"] == "agenteval"
    assert res_attrs["agent.framework"] == "langgraph"
    assert res_attrs["agent.name"] == "ReAct Agent"

    spans = _spans(payload)
    assert len(spans) == 3
    scope = payload["resourceSpans"][0]["scopeSpans"][0]["scope"]
    assert scope["name"] == "agenteval.otlp"


def test_span_ids_and_parent_chain():
    spans = _spans(to_otlp_payload(_trace()))
    by_id = {s["spanId"]: s for s in spans}

    root, llm, tool = (by_id[otlp._to_span_id(x)] for x in ("s-root", "s-llm1", "s-tool"))
    assert "parentSpanId" not in root
    assert llm["parentSpanId"] == root["spanId"]
    assert tool["parentSpanId"] == root["spanId"]
    # trace id 是定长 32 hex
    assert all(len(s["traceId"]) == 32 for s in spans)
    assert all(len(s["spanId"]) == 16 for s in spans)


def test_timestamps_are_unix_nano_strings():
    spans = _spans(to_otlp_payload(_trace()))
    root = spans[0]

    expected_start = int(
        datetime(2026, 8, 15, tzinfo=UTC).timestamp() * 1_000_000_000
    )
    expected_end = expected_start + 5 * 1_000_000_000
    assert root["startTimeUnixNano"] == str(expected_start)
    assert root["endTimeUnixNano"] == str(expected_end)


def test_llm_call_has_genai_attributes():
    spans = _spans(to_otlp_payload(_trace()))
    llm = next(s for s in spans if s["name"] == "deepseek-v4-flash")
    attrs = _attr_map(llm)

    assert attrs["gen_ai.request.model"] == "deepseek-v4-flash"
    assert attrs["gen_ai.usage.input_tokens"] == "40"
    assert attrs["gen_ai.usage.output_tokens"] == "60"
    assert attrs["gen_ai.usage.total_tokens"] == "100"
    assert attrs["span.type"] == "llm_call"


def test_error_span_status_and_event():
    spans = _spans(to_otlp_payload(_trace()))
    tool = next(s for s in spans if s["name"] == "search")

    assert tool["status"] == {"code": 2}
    assert tool["events"][0]["name"] == "exception"
    event_attrs = _attr_map(tool["events"][0])
    assert event_attrs["exception.message"] == "boom"
    # 正常 span 状态为 OK
    llm = next(s for s in spans if s["name"] == "deepseek-v4-flash")
    assert llm["status"] == {"code": 1}


def test_export_otlp_json_writes_file(tmp_path):
    db = str(tmp_path / "db.sqlite")
    init_db(db)
    insert_trace(db, _trace("t1"))

    out = tmp_path / "trace.json"
    count = export_otlp_json(db, "t1", str(out))
    assert count == 3
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(_spans(payload)) == 3

    # trace 不存在返回 0
    assert export_otlp_json(db, "nope", str(tmp_path / "x.json")) == 0


def test_send_otlp_http_posts_payload(tmp_path, monkeypatch):
    db = str(tmp_path / "db.sqlite")
    init_db(db)
    insert_trace(db, _trace("t1"))

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout=10.0):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(otlp.urllib.request, "urlopen", fake_urlopen)
    send_otlp_http(db, "t1", "http://localhost:4318/v1/traces")

    assert captured["url"] == "http://localhost:4318/v1/traces"
    assert captured["method"] == "POST"
    assert captured["content_type"] == "application/json"
    assert len(_spans(captured["body"])) == 3


def test_send_otlp_http_missing_trace_raises(tmp_path):
    db = str(tmp_path / "db.sqlite")
    init_db(db)
    with pytest.raises(LookupError):
        send_otlp_http(db, "nope", "http://localhost:4318/v1/traces")
