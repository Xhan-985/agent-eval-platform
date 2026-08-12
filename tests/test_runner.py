"""replay 执行引擎的单元测试（mock factory，不依赖真实 LLM API）。"""

import pytest
from langchain_core.messages import HumanMessage

from agenteval.replay.runner import NotReplayableError, replay_span


class _FakeLLM:
    """记录调用参数的假 LLM。"""

    def __init__(self, name: str, output: str = "replayed-answer") -> None:
        self.name = name
        self.output = output
        self.calls: list = []

    def invoke(self, input_value):
        self.calls.append(input_value)
        return self.output


class _FailingLLM:
    def invoke(self, input_value):
        raise TimeoutError("api timeout")


def _llm_span(model_name="gpt-4o", input_value=None, output=None):
    return {
        "span_id": "llm1",
        "type": "llm_call",
        "name": "ChatOpenAI",
        "input": input_value if input_value is not None else {"messages": [{"content": "hi"}]},
        "output": output if output is not None else {"text": "old-answer"},
        "error": None,
        "metadata": {"model_name": model_name, "invocation_params": {"temperature": 0}},
    }


def _tool_span():
    return {
        "span_id": "tool1",
        "type": "tool_call",
        "name": "search",
        "input": {"query": "q"},
        "output": "results",
        "error": None,
        "metadata": {"tool_call_id": "t1"},
    }


def test_llm_replay_calls_factory_with_model_name():
    llm = _FakeLLM("gpt-4o")
    factory_calls = []

    def factory(model_name):
        factory_calls.append(model_name)
        return llm

    span = _llm_span()
    result = replay_span(span, {"messages": [{"content": "new question"}]}, factory)

    assert factory_calls == ["gpt-4o"]
    assert len(llm.calls) == 1
    assert isinstance(llm.calls[0], list)
    assert isinstance(llm.calls[0][0], HumanMessage)
    assert llm.calls[0][0].content == "new question"
    assert result["replayed_output"] == "replayed-answer"
    assert result["original_output"] == {"text": "old-answer"}
    assert result["is_recorded"] is False
    assert result["error"] is None


def test_llm_replay_prefers_invocation_params_model_id():
    llm = _FakeLLM("deepseek-v4-flash")
    span = _llm_span(model_name="ChatOpenAI")
    span["metadata"]["invocation_params"] = {
        "model": "deepseek-v4-flash",
        "temperature": 0,
    }
    factory_calls = []

    def factory(model_name):
        factory_calls.append(model_name)
        return llm

    result = replay_span(span, {"messages": []}, factory)
    assert factory_calls == ["deepseek-v4-flash"]
    assert result["error"] is None


def test_llm_replay_without_new_input_uses_original():
    llm = _FakeLLM("gpt-4o")
    span = _llm_span(input_value={"messages": [{"type": "human", "content": "original"}]})
    result = replay_span(span, None, lambda name: llm)
    assert llm.calls[0][0].content == "original"
    assert result["error"] is None


def test_llm_replay_converts_dict_messages_to_basemessage_list():
    llm = _FakeLLM("gpt-4o")
    span = _llm_span(
        input_value={
            "messages": [
                {"type": "system", "content": "sys"},
                {"type": "human", "content": "hi"},
            ]
        }
    )
    result = replay_span(span, None, lambda name: llm)
    assert result["error"] is None
    assert [type(m).__name__ for m in llm.calls[0]] == ["SystemMessage", "HumanMessage"]


def test_llm_replay_without_factory_returns_clear_error():
    result = replay_span(_llm_span(), {"messages": []}, None)
    assert result["replayed_output"] is None
    assert result["is_recorded"] is False
    assert "llm_factory" in result["error"]


def test_llm_replay_catches_api_error():
    result = replay_span(_llm_span(), {"messages": []}, lambda name: _FailingLLM())
    assert result["replayed_output"] is None
    assert "TimeoutError" in result["error"]


def test_tool_replay_returns_recorded_response():
    called = []

    def factory(model_name):
        called.append(model_name)
        raise AssertionError("tool replay 不应调用 llm_factory")

    result = replay_span(_tool_span(), None, factory)
    assert result["is_recorded"] is True
    assert result["replayed_output"] == "results"
    assert result["original_output"] == "results"
    assert result["error"] is None
    assert called == []


def test_agent_run_raises_not_replayable():
    span = {"span_id": "root", "type": "agent_run", "name": "LangGraph"}
    with pytest.raises(NotReplayableError):
        replay_span(span, None, lambda name: None)


def test_node_raises_not_replayable():
    span = {"span_id": "n1", "type": "node", "name": "reason"}
    with pytest.raises(NotReplayableError):
        replay_span(span, None, lambda name: None)
