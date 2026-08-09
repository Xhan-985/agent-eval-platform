"""对外 API（init / wrap / trace / last_trace）的测试。"""

from typing import TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.graph import END, START, StateGraph

import agenteval
from agenteval.collector.callback import AgentEvalCallbackHandler


class _State(TypedDict):
    query: str
    messages: list


def _build_graph():
    llm = FakeListChatModel(responses=["done"])

    def node(state: _State) -> dict:
        resp = llm.invoke(state["query"])
        return {"messages": [resp.content]}

    g = StateGraph(_State)
    g.add_node("answer", node)
    g.add_edge(START, "answer")
    g.add_edge("answer", END)
    return g.compile()


def test_init_is_idempotent():
    agenteval.init(verbose=False)
    first = agenteval._handler
    agenteval.init(verbose=False)
    assert agenteval._handler is not None
    assert agenteval._handler is not first


def test_wrap_invokes_and_collects_trace():
    agenteval.init(verbose=False)
    wrapped = agenteval.wrap(_build_graph())
    result = wrapped.invoke({"query": "q", "messages": []})
    assert result["messages"] == ["done"]
    trace = agenteval.last_trace()
    assert trace["status"] == "success"
    assert trace["root_span"]["type"] == "agent_run"


def test_wrap_merges_user_config():
    agenteval.init(verbose=False)

    class FakeGraph:
        def __init__(self):
            self.seen_config = None

        def invoke(self, input, config=None, **kwargs):
            self.seen_config = config
            return {}

    fake = FakeGraph()
    wrapped = agenteval.wrap(fake)
    wrapped.invoke({}, config={"thread_id": "abc"})
    assert fake.seen_config["thread_id"] == "abc"
    assert fake.seen_config["callbacks"][0] is agenteval._handler


def test_wrap_ainvoke_raises_not_implemented():
    agenteval.init(verbose=False)
    wrapped = agenteval.wrap(_build_graph())
    with pytest.raises(NotImplementedError):
        wrapped.ainvoke({})


def test_wrap_stream_raises_not_implemented():
    agenteval.init(verbose=False)
    wrapped = agenteval.wrap(_build_graph())
    with pytest.raises(NotImplementedError):
        wrapped.stream({})


def test_wrap_without_init_raises(monkeypatch):
    monkeypatch.setattr(agenteval, "_handler", None)
    with pytest.raises(RuntimeError):
        agenteval.wrap(_build_graph())


def test_wrapped_error_still_records_trace():
    agenteval.init(verbose=False)

    def bad_node(state: _State) -> dict:
        raise ValueError("node exploded")

    g = StateGraph(_State)
    g.add_node("bad", bad_node)
    g.add_edge(START, "bad")
    g.add_edge("bad", END)
    wrapped = agenteval.wrap(g.compile())
    with pytest.raises(ValueError, match="node exploded"):
        wrapped.invoke({"query": "q", "messages": []})
    trace = agenteval.last_trace()
    assert trace["status"] == "error"
    assert "node exploded" in trace["root_span"]["error"]


def test_trace_decorator_passes_callbacks_via_kwargs():
    agenteval.init(verbose=False)
    seen = {}

    @agenteval.trace
    def run_agent(question, **kwargs):
        seen["callbacks"] = kwargs.get("callbacks")
        return question

    run_agent("hello")
    assert seen["callbacks"] == [agenteval._handler]


def test_multiple_invokes_produce_independent_traces():
    agenteval.init(verbose=False)
    wrapped = agenteval.wrap(_build_graph())
    wrapped.invoke({"query": "one", "messages": []})
    first_id = agenteval.last_trace()["trace_id"]
    wrapped.invoke({"query": "two", "messages": []})
    second = agenteval.last_trace()
    assert second["trace_id"] != first_id
    assert second["root_span"]["input"]["query"] == "two"


def test_handler_is_callback_handler():
    agenteval.init(verbose=False)
    assert isinstance(agenteval._handler, AgentEvalCallbackHandler)
