"""callback handler 的单元测试（用合成事件，不依赖真实 LLM）。"""

from uuid import uuid4

from langchain_core.messages import HumanMessage

from agenteval.collector.callback import AgentEvalCallbackHandler


def test_chain_start_creates_root_span():
    h = AgentEvalCallbackHandler()
    rid = uuid4()
    h.on_chain_start(
        None,
        {"query": "q"},
        run_id=rid,
        parent_run_id=None,
        tags=[],
        metadata={"langgraph_node": "root"},
        name="LangGraph",
    )
    state = h._states[str(rid)]
    assert h._root_run_id == str(rid)
    assert state["type"] == "agent_run"
    assert state["name"] == "LangGraph"
    assert state["input"] == {"query": "q"}
    assert state["started_at"] is not None


def test_chain_end_updates_output_and_ended_at():
    h = AgentEvalCallbackHandler()
    rid = uuid4()
    h.on_chain_start(None, {}, run_id=rid, parent_run_id=None, name="LangGraph")
    h.on_chain_end({"query": "q"}, run_id=rid, parent_run_id=None)
    state = h._states[str(rid)]
    assert state["output"] == {"query": "q"}
    assert state["ended_at"] is not None


def test_node_child_mapping():
    h = AgentEvalCallbackHandler()
    parent, child = uuid4(), uuid4()
    h.on_chain_start(None, {}, run_id=parent, parent_run_id=None, name="LangGraph")
    h.on_chain_start(None, {}, run_id=child, parent_run_id=parent, name="reason")
    assert h._children[str(parent)] == [str(child)]
    assert h._states[str(child)]["type"] == "node"
    assert h._states[str(child)]["name"] == "reason"


def test_chat_model_start_captures_invocation_params_and_messages():
    h = AgentEvalCallbackHandler()
    rid, pid = uuid4(), uuid4()
    h.on_chain_start(None, {}, run_id=pid, parent_run_id=None, name="LangGraph")
    h.on_chat_model_start(
        {"name": "FakeListChatModel"},
        [[HumanMessage(content="hi")]],
        run_id=rid,
        parent_run_id=pid,
        invocation_params={"temperature": 0},
        options={"stop": None},
        name=None,
        batch_size=1,
    )
    state = h._states[str(rid)]
    assert state["type"] == "llm_call"
    assert state["name"] == "FakeListChatModel"
    assert state["metadata"]["invocation_params"] == {"temperature": 0}
    assert state["input"]["messages"][0]["content"] == "hi"


def test_tool_events_capture_input_output_and_tool_call_id():
    h = AgentEvalCallbackHandler()
    rid, pid = uuid4(), uuid4()
    h.on_chain_start(None, {}, run_id=pid, parent_run_id=None, name="LangGraph")
    h.on_tool_start(
        {"name": "search", "description": "d"},
        "query",
        run_id=rid,
        parent_run_id=pid,
        tool_call_id="t1",
    )
    h.on_tool_end("results", run_id=rid, parent_run_id=pid)
    state = h._states[str(rid)]
    assert state["type"] == "tool_call"
    assert state["name"] == "search"
    assert state["input"] == "query"
    assert state["output"] == "results"
    assert state["metadata"]["tool_call_id"] == "t1"


def test_chain_error_records_error_and_ends_span():
    h = AgentEvalCallbackHandler()
    rid = uuid4()
    h.on_chain_start(None, {}, run_id=rid, parent_run_id=None, name="LangGraph")
    h.on_chain_error(ValueError("boom"), run_id=rid, parent_run_id=None)
    state = h._states[str(rid)]
    assert "boom" in state["error"]
    assert state["ended_at"] is not None


def test_callback_never_raises_on_bad_input():
    h = AgentEvalCallbackHandler()
    h.on_chain_start(None, object(), run_id=uuid4(), parent_run_id=None, name=None)
    h.on_chain_end(object(), run_id=uuid4(), parent_run_id=None)
    h.on_llm_end(None, run_id=uuid4(), parent_run_id=None)
    h.on_tool_end(object(), run_id=uuid4(), parent_run_id=None)
    h.on_chat_model_start(None, None, run_id=uuid4(), parent_run_id=None)


def test_reset_clears_all_state():
    h = AgentEvalCallbackHandler()
    h.on_chain_start(None, {}, run_id=uuid4(), parent_run_id=None, name="LangGraph")
    h.reset()
    assert h._states == {}
    assert h._children == {}
    assert h._root_run_id is None


def test_get_trace_returns_dict_with_root_span():
    h = AgentEvalCallbackHandler()
    rid = uuid4()
    h.on_chain_start(None, {}, run_id=rid, parent_run_id=None, name="LangGraph")
    h.on_chain_end({"done": True}, run_id=rid, parent_run_id=None)
    trace = h.get_trace()
    assert trace["status"] == "success"
    assert trace["root_span"]["type"] == "agent_run"
