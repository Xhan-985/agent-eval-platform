"""init/wrap 的 SQLite 持久化集成测试（不依赖真实 LLM）。"""

from typing import TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.graph import END, START, StateGraph

import agenteval
from agenteval.storage.db import get_trace, list_traces
from agenteval.storage.schema import STATUS_ERROR, STATUS_SUCCESS


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


def test_init_creates_db_file(tmp_path):
    db = str(tmp_path / "a.db")
    agenteval.init(db_path=db)
    import os

    assert os.path.exists(db)


def test_wrap_invoke_persists_trace(tmp_path):
    db = str(tmp_path / "a.db")
    agenteval.init(db_path=db)
    wrapped = agenteval.wrap(_build_graph())
    wrapped.invoke({"query": "q", "messages": []})

    rows = list_traces(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == STATUS_SUCCESS
    assert row["agent_name"] == "LangGraph"
    assert agenteval.last_trace()["trace_id"] == row["id"]


def test_wrap_agent_name_persisted(tmp_path):
    db = str(tmp_path / "a.db")
    agenteval.init(db_path=db)
    agenteval.wrap(_build_graph(), name="搜索Agent").invoke(
        {"query": "q", "messages": []}
    )
    row = get_trace(db, agenteval.last_trace()["trace_id"])
    assert row["agent_name"] == "搜索Agent"


def test_experiment_id_persisted(tmp_path):
    db = str(tmp_path / "a.db")
    agenteval.init(db_path=db, experiment_id="test1")
    agenteval.wrap(_build_graph()).invoke({"query": "q", "messages": []})
    assert get_trace(db, agenteval.last_trace()["trace_id"])["experiment_id"] == "test1"


def test_no_experiment_id_stored_as_null(tmp_path):
    db = str(tmp_path / "a.db")
    agenteval.init(db_path=db)
    agenteval.wrap(_build_graph()).invoke({"query": "q", "messages": []})
    assert get_trace(db, agenteval.last_trace()["trace_id"])["experiment_id"] is None


def test_error_trace_persisted_with_error_status(tmp_path):
    db = str(tmp_path / "a.db")
    agenteval.init(db_path=db)

    def bad_node(state: _State) -> dict:
        raise ValueError("node exploded")

    g = StateGraph(_State)
    g.add_node("bad", bad_node)
    g.add_edge(START, "bad")
    g.add_edge("bad", END)
    wrapped = agenteval.wrap(g.compile())
    with pytest.raises(ValueError):
        wrapped.invoke({"query": "q", "messages": []})

    rows = list_traces(db)
    assert len(rows) == 1
    assert rows[0]["status"] == STATUS_ERROR
