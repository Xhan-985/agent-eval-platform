"""仪表盘纯计算函数 + 时间线瀑布展平的单元测试（不依赖 streamlit）。"""

from agenteval.web.dashboard_view import (
    build_status_distribution,
    build_trend,
    compute_dashboard,
)
from agenteval.web.timeline_view import build_waterfall


def _row(tid, status, tokens=None, ms=None, spans=None, day="2026-08-12", agent="A"):
    # status 用 schema 整数：0=success, 1=error
    return {
        "id": tid,
        "created_at": f"{day}T00:00:00+00:00",
        "status": status,
        "agent_name": agent,
        "total_tokens": tokens,
        "duration_ms": ms,
        "span_count": spans,
        "experiment_id": None,
    }


def test_compute_dashboard_kpis():
    rows = [
        _row("a", 0, tokens=100, ms=2000, spans=5),
        _row("b", 0, tokens=50, ms=1000, spans=3),
        _row("c", 1, tokens=0, ms=500, spans=2),
    ]
    stats = compute_dashboard(rows)
    assert stats["total"] == 3
    assert stats["success"] == 2
    assert stats["error"] == 1
    assert stats["success_rate"] == 66.7
    assert stats["total_tokens"] == 150
    assert stats["span_total"] == 10
    assert stats["avg_duration_ms"] == 1167  # (2000+1000+500)/3
    assert stats["slowest_ms"] == 2000


def test_compute_dashboard_empty():
    stats = compute_dashboard([])
    assert stats["total"] == 0
    assert stats["success_rate"] == 0.0
    assert stats["avg_duration_ms"] is None
    assert stats["slowest_ms"] is None


def test_build_trend_groups_by_day():
    rows = [
        _row("a", 0, tokens=10, day="2026-08-10"),
        _row("b", 0, tokens=20, day="2026-08-10"),
        _row("c", 0, tokens=5, day="2026-08-12"),
    ]
    trend = build_trend(rows)
    assert [t["date"] for t in trend] == ["2026-08-10", "2026-08-12"]
    assert trend[0]["traces"] == 2
    assert trend[0]["tokens"] == 30
    assert trend[1]["traces"] == 1


def test_build_status_distribution():
    rows = [_row("a", 0), _row("b", 1), _row("c", 1)]
    dist = build_status_distribution(rows)
    assert dist == {"success": 1, "error": 2, "running": 0}


def _span(span_id, started, ended, children=None, stype="node", name="n"):
    return {
        "span_id": span_id,
        "type": stype,
        "name": name,
        "started_at": started,
        "ended_at": ended,
        "metadata": {},
        "children": children or [],
    }


def test_build_waterfall_offsets_and_durations():
    trace = {
        "root_span": _span(
            "root",
            "2026-08-12T00:00:00+00:00",
            "2026-08-12T00:00:03+00:00",
            stype="agent_run",
            name="Agent",
            children=[
                _span("a", "2026-08-12T00:00:00+00:00",
                      "2026-08-12T00:00:01+00:00", stype="llm_call"),
                _span("b", "2026-08-12T00:00:01+00:00",
                      "2026-08-12T00:00:03+00:00", stype="tool_call"),
            ],
        )
    }
    rows = build_waterfall(trace)
    assert [r["span_id"] for r in rows] == ["root", "a", "b"]
    root = rows[0]
    assert root["start_s"] == 0.0
    assert root["dur_s"] == 3.0
    assert root["depth"] == 0
    a = rows[1]
    assert a["start_s"] == 0.0
    assert a["dur_s"] == 1.0
    assert a["depth"] == 1
    assert a["type"] == "llm_call"
    b = rows[2]
    assert b["start_s"] == 1.0
    assert b["dur_s"] == 2.0


def test_build_waterfall_missing_root():
    assert build_waterfall({}) == []
    assert build_waterfall({"root_span": None}) == []
