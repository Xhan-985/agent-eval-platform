"""replay 策略判断的单元测试。"""

from agenteval.replay.policy import (
    NOT_REPLAYABLE,
    RECORDED,
    REPLAYABLE,
    get_replay_policy,
)


def test_replayable_span_types():
    assert REPLAYABLE == {"llm_call"}
    assert RECORDED == {"tool_call"}
    assert NOT_REPLAYABLE == {"agent_run", "node"}


def test_llm_call_is_realtime():
    assert get_replay_policy("llm_call") == "realtime"


def test_tool_call_is_recorded():
    assert get_replay_policy("tool_call") == "recorded"


def test_agent_run_and_node_not_supported():
    assert get_replay_policy("agent_run") == "not_supported"
    assert get_replay_policy("node") == "not_supported"


def test_unknown_type_not_supported():
    assert get_replay_policy("mystery") == "not_supported"
