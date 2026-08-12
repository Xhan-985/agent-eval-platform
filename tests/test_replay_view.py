"""replay 面板的 AppTest 测试（未安装 streamlit 时自动跳过）。"""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


class _FakeLLM:
    def __init__(self, output="new-answer") -> None:
        self.output = output

    def invoke(self, input_value):
        return self.output


def _llm_span():
    return {
        "span_id": "llm1",
        "type": "llm_call",
        "name": "ChatOpenAI",
        "input": {"messages": [{"content": "hi"}]},
        "output": {"text": "old-answer"},
        "error": None,
        "metadata": {"model_name": "gpt-4o"},
    }


def _tool_span():
    return {
        "span_id": "tool1",
        "type": "tool_call",
        "name": "search",
        "input": {"query": "q"},
        "output": "results",
        "error": None,
        "metadata": {},
    }


def _node_span():
    return {"span_id": "n1", "type": "node", "name": "reason"}


def _code(span, with_factory=True):
    factory_block = (
        "class _FakeLLM:\n"
        "    def __init__(self):\n"
        "        self.output = 'new-answer'\n"
        "    def invoke(self, input_value):\n"
        "        return self.output\n"
        "llm_factory = lambda name: _FakeLLM()\n"
    )
    if not with_factory:
        factory_block = "llm_factory = None\n"
    return (
        "import streamlit as st\n"
        "from agenteval.web.replay_view import render_replay\n"
        f"span = {span!r}\n"
        + factory_block
        + "render_replay(span, llm_factory)\n"
    )


def _run(span, with_factory=True):
    return AppTest.from_string(_code(span, with_factory), default_timeout=20).run()


def test_llm_span_shows_editable_input_and_replay_button():
    at = _run(_llm_span())
    assert not at.exception
    assert len(at.text_area) == 1
    assert len(at.button) == 1


def test_llm_replay_shows_output_comparison():
    at = _run(_llm_span())
    at.text_area[0].set_value('{"messages": [{"content": "new question"}]}')
    at.run()
    at.button[0].click()
    at.run()

    markdown_values = [m.value for m in at.markdown]
    assert any("原 output" in v for v in markdown_values)
    assert any("新 output" in v for v in markdown_values)
    # 新 output 走结构化展示（st.code），不再用 escape 文本
    code_values = [c.value for c in at.code]
    assert any("new-answer" in v for v in code_values)
    assert not at.error


def test_tool_span_shows_recorded_warning():
    at = _run(_tool_span())
    assert not at.exception
    assert at.warning and any("录播响应" in w.value for w in at.warning)
    assert len(at.button) == 0


def test_node_span_shows_not_supported():
    at = _run(_node_span())
    assert not at.exception
    assert any("不支持 replay" in m.value for m in at.markdown)
    assert len(at.button) == 0


def test_replay_with_invalid_json_shows_error():
    at = _run(_llm_span())
    at.text_area[0].set_value("{bad json")
    at.run()
    at.button[0].click()
    at.run()
    assert at.error and any("解析失败" in e.value for e in at.error)


def test_replay_without_factory_shows_clear_error():
    at = _run(_llm_span(), with_factory=False)
    at.button[0].click()
    at.run()
    assert at.error and any("llm_factory" in e.value for e in at.error)


def test_error_hint_maps_auth_failure_to_actionable_hint():
    from agenteval.web.replay_view import _error_hint

    auth = _error_hint("AuthenticationError: 401 - incorrect api key")
    assert auth and "Base URL" in auth
    conn = _error_hint("APIConnectionError: timeout contacting host")
    assert conn and "Base URL" in conn
    model = _error_hint("NotFoundError: model gpt-99 does not exist")
    assert model and "模型名" in model
    assert _error_hint("something else") is None
