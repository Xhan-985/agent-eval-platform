"""Web trace 对比页的无头测试（AppTest；未安装 streamlit 时自动跳过）。"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

import agenteval
from agenteval.storage.db import init_db, insert_trace

APP_PATH = Path(__file__).resolve().parent.parent / "agenteval" / "web" / "app.py"


def _trace(trace_id: str, status: str) -> dict:
    return {
        "trace_id": trace_id,
        "created_at": f"2026-08-15T00:00:0{0 if status == 'success' else 1}+00:00",
        "status": status,
        "framework": "langgraph",
        "agent_name": "ReAct Agent",
        "root_span": {
            "span_id": f"s-{trace_id}",
            "type": "agent_run",
            "name": "ReAct Agent",
            "input": {"query": "LangGraph 是什么？"},
            "output": {},
            "error": "boom" if status == "error" else None,
            "annotation": "a",
            "started_at": "2026-08-15T00:00:00+00:00",
            "ended_at": "2026-08-15T00:00:01+00:00",
            "metadata": {},
            "children": [],
        },
    }


def _seed(db: str) -> None:
    init_db(db)
    insert_trace(db, _trace("ok1", "success"))
    insert_trace(db, _trace("bad1", "error"))


def _goto_diff(at) -> None:
    at.radio[0].set_value("Trace 对比")
    at.run()


def test_diff_page_renders_with_two_traces(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    _goto_diff(at)

    assert not at.exception
    assert at.subheader[0].value == "Trace 对比"
    assert "trace A" in [s.label for s in at.selectbox]
    assert "trace B" in [s.label for s in at.selectbox]
    frame = at.dataframe[0].value
    assert "差异字段" in frame.columns
    assert len(frame) >= 1
    # span 列显示可读标签（类型 · 名称），不允许出现 span id
    a_span = str(frame["A span"].iloc[0])
    assert "ReAct Agent" in a_span
    assert "s-ok1" not in a_span
    # 状态指标用中文（成功/失败）
    status_values = [m.value for m in at.metric[:2]]
    assert set(status_values) == {"成功", "失败"}


def test_diff_page_with_single_trace_shows_info(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    init_db(db)
    insert_trace(db, _trace("ok1", "success"))
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    _goto_diff(at)

    assert any("至少需要两条 trace" in i.value for i in at.info)
