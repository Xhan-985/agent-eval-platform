"""列表页纯计算函数（token 聚合 / 耗时 / 行格式化）的单元测试。"""

import json

from agenteval.web.metrics import (
    aggregate_total_tokens,
    build_rows,
    extract_query_preview,
    format_duration,
    trace_duration_seconds,
    trace_select_label,
)


def _llm_span(span_id, total_tokens, children=None):
    return {
        "span_id": span_id,
        "type": "llm_call",
        "name": "ChatOpenAI",
        "input": {},
        "output": {},
        "error": None,
        "annotation": "a",
        "started_at": "2026-08-12T00:00:00+00:00",
        "ended_at": "2026-08-12T00:00:01+00:00",
        "metadata": {"token_usage": {"total_tokens": total_tokens}},
        "children": children or [],
    }


def _trace(root_span):
    return {
        "trace_id": "t1",
        "created_at": "2026-08-12T00:00:00+00:00",
        "status": "success",
        "framework": "langgraph",
        "agent_name": "LangGraph",
        "root_span": root_span,
    }


def test_aggregate_tokens_sums_nested_llm_spans():
    root = {
        "type": "agent_run",
        "children": [
            {"type": "node", "children": [_llm_span("l1", 10)]},
            _llm_span("l2", 20),
        ],
    }
    assert aggregate_total_tokens(_trace(root)) == 30


def test_aggregate_tokens_accepts_json_string():
    trace = _trace({"type": "agent_run", "children": [_llm_span("l1", 7)]})
    assert aggregate_total_tokens(json.dumps(trace, ensure_ascii=False)) == 7


def test_aggregate_tokens_missing_usage_is_zero():
    span = {"type": "llm_call", "metadata": {}, "children": []}
    assert aggregate_total_tokens(_trace(span)) == 0


def test_duration_seconds_from_root_span():
    root = {
        "type": "agent_run",
        "started_at": "2026-08-12T00:00:00+00:00",
        "ended_at": "2026-08-12T00:00:03+00:00",
        "children": [],
    }
    assert trace_duration_seconds(_trace(root)) == 3.0


def test_duration_none_when_missing():
    root = {
        "type": "agent_run",
        "started_at": "2026-08-12T00:00:00+00:00",
        "ended_at": None,
        "children": [],
    }
    assert trace_duration_seconds(_trace(root)) is None


def test_format_duration():
    assert format_duration(0.123) == "123ms"
    assert format_duration(1.5) == "1.5s"
    assert format_duration(None) == "-"


def test_extract_query_preview_from_query_field():
    root = {"type": "agent_run", "input": {"query": "LangGraph 是什么？", "messages": []}}
    assert extract_query_preview(_trace(root)) == "LangGraph 是什么？"


def test_extract_query_preview_from_messages_tuple():
    root = {"type": "agent_run", "input": {"messages": [["user", "给我讲个笑话"]]}}
    assert extract_query_preview(_trace(root)) == "给我讲个笑话"


def test_extract_query_preview_from_message_dict():
    root = {
        "type": "agent_run",
        "input": {"messages": [{"type": "human", "content": "你好"}]},
    }
    assert extract_query_preview(_trace(root)) == "你好"


def test_extract_query_preview_truncates_long_text():
    long = "问题" * 100
    root = {"type": "agent_run", "input": {"query": long}}
    preview = extract_query_preview(_trace(root))
    assert preview.endswith("…")
    assert len(preview) <= 81


def test_extract_query_preview_none_when_no_input():
    root = {"type": "agent_run", "input": {}}
    assert extract_query_preview(_trace(root)) is None


def test_build_rows_maps_fields():
    root = {
        "type": "agent_run",
        "started_at": "2026-08-12T00:00:00+00:00",
        "ended_at": "2026-08-12T00:00:02+00:00",
        "children": [_llm_span("l1", 42)],
    }
    rows = build_rows(
        [
            {
                "id": "t1",
                "created_at": "2026-08-12T00:00:00+00:00",
                "status": 0,
                "agent_name": "LangGraph",
                "trace_json": json.dumps(_trace(root), ensure_ascii=False),
                "experiment_id": "exp-a",
            },
            {
                "id": "t2",
                "created_at": "2026-08-11T00:00:00+00:00",
                "status": 1,
                "agent_name": "LangGraph",
                "trace_json": json.dumps(_trace(root), ensure_ascii=False),
                "experiment_id": None,
            },
        ]
    )
    assert rows[0] == {
        "id": "t1",
        "created_at": "2026-08-12T00:00:00+00:00",
        "status": "success",
        "agent_name": "LangGraph",
        "tokens": 42,
        "duration": "2.0s",
        "experiment_id": "exp-a",
        "query": "",
    }
    assert rows[1]["status"] == "error"
    assert rows[1]["experiment_id"] == ""
    assert rows[1]["query"] == ""


def test_trace_select_label_prefers_query_preview():
    label = trace_select_label(
        {
            "id": "b241b3a0-97c3-470b-85d3-20806a56575c",
            "agent_name": "ReAct 示例",
            "query_preview": "给我讲个笑话",
            "total_tokens": 1234,
        }
    )
    assert label == "给我讲个笑话 · ReAct 示例 · 1,234 tokens"


def test_trace_select_label_falls_back_to_agent():
    label = trace_select_label(
        {"id": "12345678-1234", "agent_name": "LangGraph", "query_preview": ""}
    )
    assert label == "LangGraph"


def test_trace_select_label_omits_zero_tokens():
    label = trace_select_label(
        {
            "id": "x",
            "agent_name": "ReAct 示例",
            "query_preview": "你好",
            "total_tokens": 0,
        }
    )
    assert label == "你好 · ReAct 示例"


def test_trace_select_label_shortens_embedded_uuid():
    label = trace_select_label(
        {
            "id": "x",
            "agent_name": "诊断助手",
            "query_preview": "请诊断 trace 59f4f97a-c584-46d1-8a13-0adaafc669d4",
            "total_tokens": 0,
        }
    )
    assert label == "请诊断 trace 59f4f97a · 诊断助手"
    assert "-c584-46d1" not in label
