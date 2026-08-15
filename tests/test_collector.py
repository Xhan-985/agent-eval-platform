"""SpanCollector 核心状态机测试（框架无关，不依赖 LangGraph/SDK）。"""

from agenteval.collector.core import SpanCollector


def _seed(collector: SpanCollector) -> None:
    collector.start_span("root", None, "agent_run", "Agent", {"query": "hi"})
    collector.start_span("llm1", "root", "llm_call", "gpt", {"messages": []})
    collector.end_span("llm1", {"text": "ok"})
    collector.end_span("root", None)


def test_start_end_builds_nested_trace():
    collector = SpanCollector(agent_name="测试")
    _seed(collector)
    trace = collector.get_trace()
    assert trace["agent_name"] == "测试"
    assert trace["framework"] == "langgraph"
    root = trace["root_span"]
    assert root["type"] == "agent_run"
    assert root["children"][0]["type"] == "llm_call"
    assert root["children"][0]["output"] == {"text": "ok"}
    assert trace["status"] == "success"


def test_error_marks_trace_error():
    collector = SpanCollector()
    collector.start_span("root", None, "agent_run", "Agent", None)
    collector.error_span("root", "boom")
    trace = collector.get_trace()
    assert trace["status"] == "error"
    assert trace["root_span"]["error"] == "boom"


def test_framework_overridable():
    collector = SpanCollector()
    collector.framework = "openai_agents"
    _seed(collector)
    assert collector.get_trace()["framework"] == "openai_agents"


def test_reset_clears_state():
    collector = SpanCollector()
    _seed(collector)
    collector.reset()
    assert collector._states == {}
    assert collector._children == {}
    assert collector._root_run_id is None


def test_empty_collector_raises():
    collector = SpanCollector()
    try:
        collector.get_trace()
    except ValueError:
        pass
    else:
        raise AssertionError("空 collector 应抛 ValueError")
