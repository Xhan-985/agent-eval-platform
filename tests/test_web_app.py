"""Streamlit 列表页的无头测试（AppTest；未安装 streamlit 时自动跳过）。"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from agenteval.storage.db import init_db, insert_trace

APP_PATH = Path(__file__).resolve().parent.parent / "agenteval" / "web" / "app.py"


def _trace(trace_id: str, status: str) -> dict:
    return {
        "trace_id": trace_id,
        "created_at": f"2026-08-12T00:00:0{0 if status == 'success' else 1}+00:00",
        "status": status,
        "framework": "langgraph",
        "agent_name": "LangGraph",
        "root_span": {
            "span_id": f"s-{trace_id}",
            "type": "agent_run",
            "name": "LangGraph",
            "input": {},
            "output": {},
            "error": "boom" if status == "error" else None,
            "annotation": "a",
            "started_at": "2026-08-12T00:00:00+00:00",
            "ended_at": "2026-08-12T00:00:01+00:00",
            "metadata": {},
            "children": [],
        },
    }


def _seed(db: str) -> None:
    init_db(db)
    insert_trace(db, _trace("ok1", "success"))
    insert_trace(db, _trace("bad1", "error"))


def test_list_page_renders_with_data(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "AgentEval — Agent 执行调试器"
    assert at.subheader[0].value == "Trace 列表"
    assert len(at.dataframe) == 1


def test_status_filter_shows_only_failed(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    at.selectbox[0].select("失败").run()
    frame = at.dataframe[0].value
    statuses = set(frame["status"].tolist())
    assert statuses == {"❌ error"}


def test_list_row_button_opens_detail(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    detail_button = next(b for b in at.button if b.label == "查看详情")
    detail_button.click()
    at.run()

    assert at.subheader[0].value.startswith("Trace 详情")
    assert len(at.get("graphviz_chart")) == 1
    assert len(at.expander) == 2


def test_detail_back_button_returns_to_list(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    at.session_state["selected_trace_id"] = "ok1"
    at.run()
    assert at.subheader[0].value.startswith("Trace 详情")

    back_button = next(b for b in at.button if b.label == "← 返回列表")
    back_button.click()
    at.run()
    assert at.subheader[0].value == "Trace 列表"
