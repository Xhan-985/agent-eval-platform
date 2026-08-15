"""Langfuse 兼容导出（to_langfuse_payload / export_to_jsonl）的单元测试。"""

import json

from agenteval.export.langfuse import export_to_jsonl, to_langfuse_payload
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
                    "metadata": {"token_usage": {"total_tokens": 100}},
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


def test_to_langfuse_payload_maps_trace():
    payload = to_langfuse_payload(_trace())

    assert len(payload["traces"]) == 1
    trace = payload["traces"][0]
    assert trace["id"] == "t1"
    assert trace["timestamp"] == "2026-08-15T00:00:00+00:00"
    assert trace["name"] == "ReAct Agent"
    assert trace["input"] == {"query": "LangGraph 是什么？"}
    assert trace["metadata"]["status"] == "error"
    assert trace["metadata"]["span_count"] == 3


def test_to_langfuse_payload_maps_observations():
    payload = to_langfuse_payload(_trace())

    obs = payload["observations"]
    assert len(obs) == 3
    assert obs[0]["id"] == "s-root"
    assert obs[0]["parentObservationId"] is None
    assert obs[0]["type"] == "SPAN"
    assert obs[1]["type"] == "GENERATION"
    assert obs[1]["parentObservationId"] == "s-root"
    assert obs[1]["metadata"]["token_usage"]["total_tokens"] == 100
    assert obs[2]["type"] == "SPAN"
    assert obs[2]["level"] == "ERROR"
    assert obs[2]["metadata"]["error"] == "boom"


def test_export_to_jsonl_writes_records(tmp_path):
    db = str(tmp_path / "e.db")
    init_db(db)
    insert_trace(db, _trace("t1"))
    out = tmp_path / "export.jsonl"

    count = export_to_jsonl(db, "t1", str(out))

    assert count == 4
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    first = json.loads(lines[0])
    assert first["kind"] == "trace"
    assert first["id"] == "t1"
    assert json.loads(lines[1])["kind"] == "observation"
    assert json.loads(lines[1])["traceId"] == "t1"


def test_export_missing_trace_returns_zero(tmp_path):
    db = str(tmp_path / "e.db")
    init_db(db)

    assert export_to_jsonl(db, "nope", str(tmp_path / "x.jsonl")) == 0
