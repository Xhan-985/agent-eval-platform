"""OpenAI Agents SDK 适配器测试（构造假 span 对象，不调用真实 API）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("agents")

from agenteval.collector.agents_sdk_adapter import AgentEvalTracingProcessor


class FakeData:
    def __init__(self, type_: str, **kwargs) -> None:
        self.type = type_
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeSpan:
    def __init__(
        self,
        span_id: str,
        trace_id: str,
        parent_id: str | None,
        data: FakeData,
        *,
        error: dict | None = None,
    ) -> None:
        self.span_id = span_id
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.span_data = data
        self.error = error
        self.started_at = "2026-08-15T00:00:00+00:00"
        self.ended_at = "2026-08-15T00:00:01+00:00"


class FakeTrace:
    def __init__(self, trace_id: str, name: str = "研究助手") -> None:
        self.trace_id = trace_id
        self.name = name


def _processor() -> tuple[AgentEvalTracingProcessor, list[dict]]:
    saved: list[dict] = []
    return AgentEvalTracingProcessor(saved.append), saved


def _run_full_trace(proc: AgentEvalTracingProcessor, trace_id: str = "t1") -> None:
    proc.on_trace_start(FakeTrace(trace_id))
    root = FakeSpan("s-root", trace_id, None, FakeData("agent", name="研究助手"))
    gen = FakeSpan(
        "s-llm",
        trace_id,
        "s-root",
        FakeData(
            "generation",
            input=[{"role": "user", "content": "你好"}],
            output=[{"role": "assistant", "content": "你好！"}],
            model="gpt-4o-mini",
            model_config={"model": "gpt-4o-mini"},
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        ),
    )
    tool = FakeSpan(
        "s-tool",
        trace_id,
        "s-root",
        FakeData("function", name="search", input='{"q": "x"}', output="结果"),
    )
    for span in (root, gen, tool):
        proc.on_span_start(span)
    proc.on_span_end(gen)
    proc.on_span_end(tool)
    proc.on_span_end(root)
    proc.on_trace_end(FakeTrace(trace_id))


def test_builds_langgraph_compatible_trace():
    proc, saved = _processor()
    _run_full_trace(proc)
    assert len(saved) == 1
    trace = saved[0]
    assert trace["framework"] == "openai_agents"
    assert trace["agent_name"] == "研究助手"
    assert trace["status"] == "success"
    root = trace["root_span"]
    assert root["type"] == "agent_run"
    assert {child["type"] for child in root["children"]} == {"llm_call", "tool_call"}
    llm = next(child for child in root["children"] if child["type"] == "llm_call")
    assert llm["metadata"]["model_version"] == "gpt-4o-mini"
    assert llm["metadata"]["token_usage"]["total_tokens"] == 15
    # 根 span 用首个 llm 输入补齐，便于 Web 对话预览
    assert root["input"] == {"messages": [{"type": "human", "content": "你好"}]}


def test_error_span_marks_trace_error():
    proc, saved = _processor()
    proc.on_trace_start(FakeTrace("t1"))
    root = FakeSpan("s-root", "t1", None, FakeData("agent", name="A"))
    gen = FakeSpan(
        "s-llm",
        "t1",
        "s-root",
        FakeData("generation", input=None, output=None, model="gpt-4o-mini"),
        error={"message": "boom", "data": None},
    )
    proc.on_span_start(root)
    proc.on_span_start(gen)
    proc.on_span_end(gen)
    proc.on_span_end(root)
    proc.on_trace_end(FakeTrace("t1"))
    trace = saved[0]
    assert trace["status"] == "error"
    llm = trace["root_span"]["children"][0]
    assert llm["error"] == "boom"


def test_nested_agent_span_is_node():
    proc, saved = _processor()
    proc.on_trace_start(FakeTrace("t1"))
    root = FakeSpan("s-root", "t1", None, FakeData("agent", name="主"))
    sub = FakeSpan("s-sub", "t1", "s-root", FakeData("agent", name="子代理"))
    proc.on_span_start(root)
    proc.on_span_start(sub)
    proc.on_span_end(sub)
    proc.on_span_end(root)
    proc.on_trace_end(FakeTrace("t1"))
    children = saved[0]["root_span"]["children"]
    assert len(children) == 1
    assert children[0]["type"] == "node"
    assert children[0]["name"] == "子代理"


def test_real_sdk_structure_flattens_to_agent_root():
    """task/turn 是包装：agent 提升为根，response 映射为 llm_call。"""
    proc, saved = _processor()
    proc.on_trace_start(FakeTrace("t1", name="Agent workflow"))
    task = FakeSpan("s-task", "t1", None, FakeData("task", name="Agent workflow"))
    agent = FakeSpan("s-agent", "t1", "s-task", FakeData("agent", name="冒烟测试"))
    turn = FakeSpan("s-turn", "t1", "s-agent", FakeData("turn"))
    response = FakeSpan(
        "s-resp",
        "t1",
        "s-turn",
        FakeData(
            "response",
            response=SimpleNamespace(model="deepseek-v4-flash", text="收到"),
            input=[{"role": "user", "content": "你好"}],
            usage={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        ),
    )
    for span in (task, agent, turn, response):
        proc.on_span_start(span)
    for span in (response, turn, agent, task):
        proc.on_span_end(span)
    proc.on_trace_end(FakeTrace("t1"))

    trace = saved[0]
    assert trace["agent_name"] == "冒烟测试"
    root = trace["root_span"]
    assert root["type"] == "agent_run"
    assert root["name"] == "冒烟测试"
    assert len(root["children"]) == 1
    llm = root["children"][0]
    assert llm["type"] == "llm_call"
    assert llm["name"] == "deepseek-v4-flash"
    assert llm["metadata"]["model_version"] == "deepseek-v4-flash"
    assert llm["metadata"]["token_usage"]["total_tokens"] == 8
    assert llm["output"] == {"text": "收到"}
    assert root["input"] == {"messages": [{"type": "human", "content": "你好"}]}


def test_multi_turn_tool_flow_is_sequential_under_agent():
    proc, saved = _processor()
    proc.on_trace_start(FakeTrace("t1", name="w"))
    task = FakeSpan("s-task", "t1", None, FakeData("task", name="w"))
    agent = FakeSpan("s-agent", "t1", "s-task", FakeData("agent", name="A"))
    turn1 = FakeSpan("s-turn1", "t1", "s-agent", FakeData("turn"))
    resp1 = FakeSpan(
        "s-resp1",
        "t1",
        "s-turn1",
        FakeData(
            "response",
            response=SimpleNamespace(model="m1", text="查一下"),
            input=[{"role": "user", "content": "q1"}],
            usage={},
        ),
    )
    func = FakeSpan(
        "s-func",
        "t1",
        "s-turn1",
        FakeData("function", name="search", input="q", output="结果"),
    )
    turn2 = FakeSpan("s-turn2", "t1", "s-agent", FakeData("turn"))
    resp2 = FakeSpan(
        "s-resp2",
        "t1",
        "s-turn2",
        FakeData(
            "response",
            response=SimpleNamespace(model="m1", text="答案"),
            input=[{"role": "user", "content": "q2"}],
            usage={},
        ),
    )
    for span in (task, agent, turn1, resp1, func, turn2, resp2):
        proc.on_span_start(span)
    for span in (resp1, func, turn1, resp2, turn2, agent, task):
        proc.on_span_end(span)
    proc.on_trace_end(FakeTrace("t1"))

    root = saved[0]["root_span"]
    children = root["children"]
    assert [child["type"] for child in children] == ["llm_call", "tool_call", "llm_call"]
    assert children[1]["name"] == "search"


def test_multiple_traces_are_isolated():
    proc, saved = _processor()
    proc.on_trace_start(FakeTrace("a", name="A"))
    proc.on_trace_start(FakeTrace("b", name="B"))
    span_a = FakeSpan("sa", "a", None, FakeData("agent", name="A"))
    span_b = FakeSpan("sb", "b", None, FakeData("agent", name="B"))
    proc.on_span_start(span_a)
    proc.on_span_start(span_b)
    proc.on_span_end(span_a)
    proc.on_span_end(span_b)
    proc.on_trace_end(FakeTrace("a"))
    proc.on_trace_end(FakeTrace("b"))
    assert len(saved) == 2
    names = {t["agent_name"] for t in saved}
    assert names == {"A", "B"}


def test_trace_without_spans_does_not_persist():
    proc, saved = _processor()
    proc.on_trace_start(FakeTrace("t1"))
    proc.on_trace_end(FakeTrace("t1"))
    assert saved == []


def test_init_registers_agents_processor(tmp_path, monkeypatch):
    import agenteval

    db = str(tmp_path / "sdk.db")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agenteval.init(db_path=db, agents_sdk=True)
    assert agenteval._agents_processor is not None
    agenteval.init(db_path=db)
    assert agenteval._agents_processor is None
