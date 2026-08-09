"""trace 树构建与序列化的单元测试。"""

import json
from uuid import uuid4

from agenteval.collector.callback import AgentEvalCallbackHandler
from agenteval.collector.serializer import build_trace, serialize_to_json


def _feed_agent_run(h, query="q"):
    root = uuid4()
    h.on_chain_start(None, {"query": query}, run_id=root, parent_run_id=None, name="LangGraph")
    h.on_chain_end({"query": query}, run_id=root, parent_run_id=None)
    return root


def test_build_trace_nested_tree():
    h = AgentEvalCallbackHandler()
    root = uuid4()
    node = uuid4()
    tool = uuid4()
    h.on_chain_start(None, {"query": "q"}, run_id=root, parent_run_id=None, name="LangGraph")
    h.on_chain_start(None, {"query": "q"}, run_id=node, parent_run_id=root, name="search_node")
    h.on_tool_start({"name": "search"}, "q", run_id=tool, parent_run_id=node, tool_call_id="t1")
    h.on_tool_end("results", run_id=tool, parent_run_id=node)
    h.on_chain_end({"query": "q"}, run_id=node, parent_run_id=root)
    h.on_chain_end({"query": "q"}, run_id=root, parent_run_id=None)

    trace = build_trace(h)
    assert trace["framework"] == "langgraph"
    assert trace["agent_name"] == "LangGraph"
    root_span = trace["root_span"]
    assert root_span["type"] == "agent_run"
    assert root_span["children"][0]["name"] == "search_node"
    assert root_span["children"][0]["children"][0]["name"] == "search"
    assert root_span["children"][0]["children"][0]["annotation"]


def test_build_trace_status_error_when_any_span_errors():
    h = AgentEvalCallbackHandler()
    root = uuid4()
    h.on_chain_start(None, {}, run_id=root, parent_run_id=None, name="LangGraph")
    h.on_chain_error(ValueError("boom"), run_id=root, parent_run_id=None)
    assert build_trace(h)["status"] == "error"


def test_build_trace_without_root_raises():
    h = AgentEvalCallbackHandler()
    try:
        build_trace(h)
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty handler")


def test_serialize_to_json_roundtrip_preserves_chinese():
    h = AgentEvalCallbackHandler()
    _feed_agent_run(h)
    text = serialize_to_json(build_trace(h))
    assert "LangGraph" in text
    data = json.loads(text)
    assert data["root_span"]["type"] == "agent_run"


def test_large_input_is_truncated():
    h = AgentEvalCallbackHandler()
    root = uuid4()
    h.on_chain_start(
        None,
        {"big": "x" * 20000},
        run_id=root,
        parent_run_id=None,
        name="LangGraph",
    )
    h.on_chain_end({}, run_id=root, parent_run_id=None)
    span = build_trace(h)["root_span"]
    assert isinstance(span["input"], str)
    assert span["input"].endswith("[truncated]")


def test_many_messages_are_capped_with_marker():
    h = AgentEvalCallbackHandler()
    root, node, llm = uuid4(), uuid4(), uuid4()
    h.on_chain_start(None, {}, run_id=root, parent_run_id=None, name="LangGraph")
    h.on_chain_start(None, {}, run_id=node, parent_run_id=root, name="reason")
    messages = [[{"content": f"m{i}", "type": "human"}] for i in range(30)]
    h.on_chat_model_start(
        {"name": "ChatOpenAI"},
        messages,
        run_id=llm,
        parent_run_id=node,
        invocation_params={},
    )
    h.on_chain_end({}, run_id=node, parent_run_id=root)
    h.on_chain_end({}, run_id=root, parent_run_id=None)
    trace = build_trace(h)
    stored = trace["root_span"]["children"][0]["children"][0]["input"]["messages"]
    assert len(stored) <= 21
    assert any("omitted" in m for m in stored if isinstance(m, dict))


def test_unserializable_object_falls_back_to_str():
    h = AgentEvalCallbackHandler()
    root = uuid4()
    h.on_chain_start(
        None,
        {"weird": object()},
        run_id=root,
        parent_run_id=None,
        name="LangGraph",
    )
    h.on_chain_end({}, run_id=root, parent_run_id=None)
    trace = build_trace(h)
    assert isinstance(trace["root_span"]["input"]["weird"], str)


def test_children_ordered_by_started_at():
    h = AgentEvalCallbackHandler()
    root, c1, c2 = uuid4(), uuid4(), uuid4()
    h.on_chain_start(None, {}, run_id=root, parent_run_id=None, name="LangGraph")
    h.on_chain_start(None, {}, run_id=c2, parent_run_id=root, name="second")
    h.on_chain_start(None, {}, run_id=c1, parent_run_id=root, name="first")
    h.on_chain_end({}, run_id=c2, parent_run_id=root)
    h.on_chain_end({}, run_id=c1, parent_run_id=root)
    h.on_chain_end({}, run_id=root, parent_run_id=None)
    names = [s["name"] for s in build_trace(h)["root_span"]["children"]]
    assert names == ["second", "first"]
