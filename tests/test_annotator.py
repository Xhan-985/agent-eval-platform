"""教学注释生成器的单元测试。"""

from agenteval.collector.annotator import annotate


def test_agent_run_annotation_contains_goal():
    span = {
        "type": "agent_run",
        "name": "LangGraph",
        "input": {"messages": [{"content": "什么是 LangGraph？"}]},
        "output": {},
        "error": None,
    }
    ann = annotate(span)
    assert "一次完整执行" in ann
    assert "LangGraph" in ann


def test_agent_run_annotation_falls_back_to_query_key():
    span = {
        "type": "agent_run",
        "name": "LangGraph",
        "input": {"query": "什么是 Agent？"},
        "output": {},
        "error": None,
    }
    ann = annotate(span)
    assert "什么是 Agent？" in ann


def test_node_annotation_mentions_node_name():
    span = {"type": "node", "name": "reason", "input": {}, "output": {}, "error": None}
    ann = annotate(span)
    assert "reason" in ann


def test_llm_call_annotation_mentions_model_and_decision():
    span = {
        "type": "llm_call",
        "name": "ChatOpenAI",
        "input": {},
        "output": {"content": "我决定调用搜索工具"},
        "error": None,
    }
    ann = annotate(span)
    assert "ChatOpenAI" in ann
    assert "搜索" in ann


def test_llm_call_annotation_extracts_text_output():
    span = {
        "type": "llm_call",
        "name": "gpt-4o-mini",
        "input": {},
        "output": {"text": "我决定搜索"},
        "error": None,
    }
    ann = annotate(span)
    assert "我决定搜索" in ann


def test_tool_call_annotation_mentions_tool_and_result():
    span = {
        "type": "tool_call",
        "name": "search",
        "input": {"query": "LangGraph 教程"},
        "output": "找到 3 条结果",
        "error": None,
    }
    ann = annotate(span)
    assert "search" in ann
    assert "3 条结果" in ann


def test_error_annotation_contains_error_and_hint():
    span = {
        "type": "tool_call",
        "name": "search",
        "input": {},
        "output": None,
        "error": "ValueError: tool exploded",
    }
    ann = annotate(span)
    assert "出错" in ann
    assert "tool exploded" in ann


def test_unknown_type_falls_back_to_generic():
    span = {"type": "mystery", "name": "x", "input": {}, "output": {}, "error": None}
    assert annotate(span) == "Agent 执行了一步操作"


def test_summarize_truncates_long_output():
    span = {
        "type": "tool_call",
        "name": "search",
        "input": {"query": "q"},
        "output": "长" * 100,
        "error": None,
    }
    ann = annotate(span)
    assert len(ann) <= 200


def test_annotation_not_more_than_two_sentences():
    span = {
        "type": "llm_call",
        "name": "gpt-4o-mini",
        "input": {},
        "output": {"content": "a" * 200},
        "error": None,
    }
    ann = annotate(span)
    assert ann.count("。") <= 2
