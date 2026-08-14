"""Streamlit 列表页的无头测试（AppTest；未安装 streamlit 时自动跳过）。"""

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


def _goto_list(at) -> None:
    """默认落地仪表盘；切到 Trace 列表视图。"""
    at.radio[0].set_value("Trace 列表")
    at.run()


def test_dashboard_renders_on_landing(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "AgentEval — Agent 执行调试器"
    # 默认落地仪表盘，有 KPI metric 与趋势图
    assert at.subheader[0].value == "仪表盘"
    assert len(at.metric) >= 5


def test_list_page_renders_with_data(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not at.exception
    _goto_list(at)
    assert at.subheader[0].value == "Trace 列表"
    assert len(at.dataframe) == 1
    view_button = next(b for b in at.button if b.label == "查看选中 Trace 详情")
    assert view_button.disabled


def test_status_filter_shows_only_failed(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    _goto_list(at)
    at.selectbox[0].select("失败").run()
    frame = at.dataframe[0].value
    statuses = set(frame["状态"].tolist())
    assert statuses == {"❌ 失败"}


def test_selecting_trace_opens_detail(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    # 选中某条 trace（列表行选中在 AppTest 中难以模拟，直接置 selected_trace_id）
    at.session_state["selected_trace_id"] = "ok1"
    at.run()

    assert at.subheader[0].value.startswith("Trace 详情")
    assert len(at.get("graphviz_chart")) == 1
    assert len(at.expander) == 2


def test_detail_back_button_returns_to_list(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    _goto_list(at)
    at.session_state["selected_trace_id"] = "ok1"
    at.run()
    assert at.subheader[0].value.startswith("Trace 详情")

    back_button = next(b for b in at.button if b.label == "← 返回列表")
    back_button.click()
    at.run()
    assert at.subheader[0].value == "Trace 列表"


def test_replay_sidebar_renders_config_inputs(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not at.exception
    labels = [t.label for t in at.text_input]
    assert "数据库路径" in labels
    assert "API Base URL" in labels
    assert "API Key" in labels
    assert "模型名" in [s.label for s in at.selectbox]
    assert agenteval._llm_factory is None


def test_replay_sidebar_with_api_key_registers_factory(tmp_path, monkeypatch):
    db = str(tmp_path / "web.db")
    _seed(db)
    monkeypatch.setenv("AGENTEVAL_DB", db)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agenteval, "_llm_factory", None)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    api_key_input = next(t for t in at.text_input if t.label == "API Key")
    api_key_input.set_value("sk-test")
    at.run()
    assert not at.exception
    assert agenteval._llm_factory is not None
