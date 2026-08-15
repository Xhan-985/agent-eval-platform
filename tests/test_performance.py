"""性能归因纯函数（span 耗时/token 占比、成本估算）的单元测试。"""

from agenteval.collector.metrics import (
    build_span_performance,
    estimate_cost,
    span_cost,
    span_duration_ms,
    span_total_tokens,
)


def _span(
    span_id: str,
    type_: str,
    name: str,
    started: str = "2026-08-15T00:00:00+00:00",
    ended: str = "2026-08-15T00:00:01+00:00",
    metadata: dict | None = None,
    error: str | None = None,
    children: list | None = None,
) -> dict:
    return {
        "span_id": span_id,
        "type": type_,
        "name": name,
        "started_at": started,
        "ended_at": ended,
        "metadata": metadata or {},
        "error": error,
        "children": children or [],
    }


def _llm(span_id: str, tokens: int, started: str, ended: str, model: str = "deepseek-v4-flash") -> dict:
    return _span(
        span_id,
        "llm_call",
        "ChatOpenAI",
        started=started,
        ended=ended,
        metadata={
            "model_name": model,
            "token_usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": tokens},
        },
    )


def test_span_duration_ms():
    assert span_duration_ms(_span("s", "node", "n")) == 1000
    assert span_duration_ms(_span("s", "node", "n", ended=None)) is None


def test_span_total_tokens_only_counts_llm_call():
    assert span_total_tokens(_llm("l", 100, "2026-08-15T00:00:00+00:00", "2026-08-15T00:00:01+00:00")) == 100
    assert span_total_tokens(_span("t", "tool_call", "search")) == 0


def test_build_span_performance_attribution_and_sort():
    root = _span(
        "root",
        "agent_run",
        "ReAct Agent",
        ended="2026-08-15T00:00:03+00:00",
        children=[
            _llm("l1", 100, "2026-08-15T00:00:00+00:00", "2026-08-15T00:00:01+00:00"),
            _span(
                "t1",
                "tool_call",
                "search",
                started="2026-08-15T00:00:01+00:00",
                ended="2026-08-15T00:00:03+00:00",
                error="boom",
            ),
        ],
    )

    rows = build_span_performance(root)

    assert [r["span_id"] for r in rows] == ["root", "t1", "l1"]  # 按耗时降序
    assert rows[0]["duration_pct"] == 100.0
    assert rows[1]["duration_pct"] == 66.7  # 2s / 3s
    assert rows[2]["duration_pct"] == 33.3  # 1s / 3s
    assert rows[2]["tokens"] == 100
    assert rows[2]["tokens_pct"] == 100.0
    assert rows[1]["error"] == "boom"
    assert rows[1]["tokens_pct"] == 0.0


def test_build_span_performance_empty():
    assert build_span_performance(None) == []


def test_estimate_cost_with_pricing():
    trace = {
        "trace_id": "t1",
        "root_span": _span(
            "root",
            "agent_run",
            "ReAct Agent",
            children=[_llm("l1", 1500, "2026-08-15T00:00:00+00:00", "2026-08-15T00:00:01+00:00")],
        ),
    }
    pricing = {"deepseek-v4-flash": {"input": 0.5, "output": 1.0}}  # 每百万 token 美元
    cost = estimate_cost(trace, pricing)
    assert round(cost, 6) == 0.001  # 1000/1e6*0.5 + 500/1e6*1.0


def test_estimate_cost_unknown_model_zero():
    trace = {
        "trace_id": "t1",
        "root_span": _span(
            "root",
            "agent_run",
            "ReAct Agent",
            children=[_llm("l1", 100, "2026-08-15T00:00:00+00:00", "2026-08-15T00:00:01+00:00")],
        ),
    }
    assert estimate_cost(trace, {"other-model": {"input": 1, "output": 1}}) == 0.0


def test_span_cost_per_span():
    pricing = {"deepseek-v4-flash": {"input": 0.5, "output": 1.0}}
    llm = _llm("l1", 1500, "2026-08-15T00:00:00+00:00", "2026-08-15T00:00:01+00:00")
    assert round(span_cost(llm, pricing), 6) == 0.001
    assert span_cost(_span("t", "tool_call", "search"), pricing) == 0.0
