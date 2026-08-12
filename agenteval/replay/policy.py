"""replay 策略：判断 span 类型对应哪种 replay 方式。"""

REPLAYABLE = {"llm_call"}
RECORDED = {"tool_call"}
NOT_REPLAYABLE = {"agent_run", "node"}


def get_replay_policy(span_type: str) -> str:
    """返回 'realtime' / 'recorded' / 'not_supported'。"""
    if span_type in REPLAYABLE:
        return "realtime"
    if span_type in RECORDED:
        return "recorded"
    return "not_supported"
