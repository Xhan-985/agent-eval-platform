"""Web 诊断页（AI 助教）的无头测试（AppTest；未安装 streamlit 时自动跳过）。"""

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


def _goto_diagnose(at) -> None:
    at.radio[0].set_value("AI 诊断")
    at.run()


def test_diagnose_page_renders_with_traces(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    _goto_diagnose(at)

    assert not at.exception
    assert at.subheader[0].value == "AI 诊断"
    assert "选择 trace" in [s.label for s in at.selectbox]
    assert "对比第二条 trace（可选）" in [s.label for s in at.selectbox]
    assert any(b.label == "开始诊断" for b in at.button)


def test_diagnose_page_without_traces_shows_info(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    init_db(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    _goto_diagnose(at)

    assert any("暂无 trace" in i.value for i in at.info)


def test_diagnose_page_without_api_key_warns(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    _goto_diagnose(at)
    run_button = next(b for b in at.button if b.label == "开始诊断")
    run_button.click()
    at.run()

    assert any("API Key" in w.value for w in at.warning)


def test_detail_has_diagnose_button_jumps_to_page(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    at.session_state["selected_trace_id"] = "ok1"
    at.run()

    diag_button = next(b for b in at.button if b.label == "用 AI 诊断这条 trace")
    diag_button.click()
    at.run()

    assert at.subheader[0].value == "AI 诊断"


def test_dashboard_has_prominent_diagnose_entry(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    diagnose_button = next(b for b in at.button if b.label == "开始 AI 诊断 →")
    diagnose_button.click()
    at.run()

    assert at.subheader[0].value == "AI 诊断"


def test_list_page_has_diagnose_entry(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    at.radio[0].set_value("Trace 列表")
    at.run()

    diagnose_button = next(b for b in at.button if b.label == "🤖 AI 诊断")
    diagnose_button.click()
    at.run()

    assert at.subheader[0].value == "AI 诊断"


def test_dashboard_has_prominent_diff_entry(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    diff_button = next(b for b in at.button if b.label == "开始对比 →")
    diff_button.click()
    at.run()

    assert at.subheader[0].value == "Trace 对比"


def test_list_page_has_diff_entry(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    at.radio[0].set_value("Trace 列表")
    at.run()

    diff_button = next(b for b in at.button if b.label == "⇄ Trace 对比")
    diff_button.click()
    at.run()

    assert at.subheader[0].value == "Trace 对比"
