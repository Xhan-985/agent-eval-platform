"""大 trace 性能基准：合成 100/500/1000 span，测量各关键操作耗时。

用法：python benchmarks/benchmark_large_trace.py
输出：每个规模的插入/列表/详情/摘要/树/瀑布/对比/归因耗时（毫秒）。
基线记录在 docs/PERF_BASELINE.md，作为 V3-P0 性能分析的验收参照。
"""

from __future__ import annotations

import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agenteval.collector.metrics import build_span_performance
from agenteval.diagnose.tools import compare_traces
from agenteval.diagnose.tools import get_trace as diagnose_summary
from agenteval.storage.db import get_trace, init_db, insert_trace, list_traces
from agenteval.web.timeline_view import build_waterfall
from agenteval.web.trace_view import build_dot

BASE = datetime(2026, 8, 15, tzinfo=UTC)


def _ts(offset_s: int) -> str:
    return (BASE + timedelta(seconds=offset_s)).isoformat()


def _span(
    span_id: str,
    type_: str,
    name: str,
    start_s: int,
    end_s: int,
    error: str | None = None,
    tokens: int | None = None,
    children: list | None = None,
) -> dict[str, Any]:
    meta = {}
    if tokens is not None:
        meta["token_usage"] = {
            "prompt_tokens": tokens,
            "completion_tokens": tokens // 2,
            "total_tokens": tokens,
        }
    return {
        "span_id": span_id,
        "type": type_,
        "name": name,
        "input": {"query": "LangGraph 是什么？"},
        "output": {"text": f"out-{name}"},
        "error": error,
        "annotation": f"教学注释：{name} 这一步在决定是否调用工具。",
        "started_at": _ts(start_s),
        "ended_at": _ts(end_s),
        "metadata": meta,
        "children": children or [],
    }


def build_synthetic_trace(trace_id: str, span_count: int) -> dict[str, Any]:
    """构造 span_count 个 span 的合成 trace（root + 若干 节点/模型/工具 链）。"""
    per_chain = 3
    chains = max(1, (span_count - 1) // per_chain)
    node_names = ("reason", "search", "plan", "router")
    tool_names = ("search", "calculator")
    children: list[dict[str, Any]] = []
    for c in range(chains):
        base_s = c * 3
        idx = c + 1
        node = _span(
            f"n{idx}",
            "node",
            node_names[c % len(node_names)],
            base_s,
            base_s,
        )
        llm = _span(
            f"l{idx}",
            "llm_call",
            "ChatOpenAI",
            base_s,
            base_s + 1,
            tokens=100 + c,
        )
        tool = _span(
            f"t{idx}",
            "tool_call",
            tool_names[c % len(tool_names)],
            base_s + 1,
            base_s + 2,
            error="模拟超时" if idx % 7 == 0 else None,
        )
        children.append(
            _span(
                f"c{idx}",
                "node",
                "chain",
                base_s,
                base_s + 2,
                children=[node, llm, tool],
            )
        )
    root = _span("root", "agent_run", "ReAct Agent", 0, chains * 3 + 5, children=children)
    return {
        "trace_id": trace_id,
        "created_at": _ts(0),
        "status": "success",
        "framework": "langgraph",
        "agent_name": "ReAct Agent",
        "root_span": root,
    }


def timed(fn, *args, **kwargs) -> tuple[float, Any]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return (time.perf_counter() - start) * 1000, result


def main() -> None:
    header = (
        f"{'span 数':>8} {'实际':>6} {'插入':>8} {'列表':>8} {'详情':>8} "
        f"{'摘要':>8} {'树':>7} {'瀑布':>7} {'对比':>8} {'归因':>8}  （毫秒）"
    )
    print(header)
    print("-" * len(header))
    for size in (100, 500, 1000):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "bench.db")
            init_db(db)
            trace_a = build_synthetic_trace(f"bench-a-{size}", size)
            trace_b = build_synthetic_trace(f"bench-b-{size}", size)
            actual = _count_spans(trace_a["root_span"])
            insert_ms, _ = timed(insert_trace, db, trace_a)
            timed(insert_trace, db, trace_b)
            list_ms, _ = timed(list_traces, db)
            detail_ms, _ = timed(get_trace, db, trace_a["trace_id"])
            summary_ms, _ = timed(diagnose_summary, db, trace_a["trace_id"])
            dot_ms, _ = timed(build_dot, trace_a)
            waterfall_ms, _ = timed(build_waterfall, trace_a)
            compare_ms, _ = timed(
                compare_traces, db, trace_a["trace_id"], trace_b["trace_id"]
            )
            perf_ms, _ = timed(build_span_performance, trace_a["root_span"])
            print(
                f"{size:>8} {actual:>6} {insert_ms:>8.1f} {list_ms:>8.1f} "
                f"{detail_ms:>8.1f} {summary_ms:>8.1f} {dot_ms:>7.1f} "
                f"{waterfall_ms:>7.1f} {compare_ms:>8.1f} {perf_ms:>8.1f}"
            )


def _count_spans(span: dict[str, Any]) -> int:
    return 1 + sum(_count_spans(child) for child in span.get("children") or [])


if __name__ == "__main__":
    main()
