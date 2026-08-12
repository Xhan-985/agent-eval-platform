"""SQLite CRUD 的单元测试（用临时目录数据库，不依赖真实 LLM）。"""

import json
import sqlite3

from agenteval.storage.db import get_trace, init_db, insert_trace, list_traces
from agenteval.storage.schema import STATUS_ERROR, STATUS_SUCCESS


def _trace(trace_id="t1", status="success", created_at="2026-08-12T00:00:00+00:00"):
    return {
        "trace_id": trace_id,
        "created_at": created_at,
        "status": status,
        "framework": "langgraph",
        "agent_name": "LangGraph",
        "root_span": {
            "span_id": f"s-{trace_id}",
            "type": "agent_run",
            "name": "LangGraph",
            "input": {},
            "output": {},
            "error": None,
            "annotation": "a",
            "started_at": created_at,
            "ended_at": created_at,
            "metadata": {},
            "children": [],
        },
    }


def test_init_db_creates_file_and_traces_table(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    assert db.exists()
    conn = sqlite3.connect(str(db))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    assert "traces" in tables


def test_init_db_is_idempotent(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    init_db(db)  # 第二次调用不应报错


def test_insert_and_get_trace(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    insert_trace(db, _trace(trace_id="t1"))
    row = get_trace(db, "t1")
    assert row["id"] == "t1"
    assert row["status"] == STATUS_SUCCESS
    assert row["agent_name"] == "LangGraph"
    assert json.loads(row["trace_json"])["trace_id"] == "t1"


def test_error_status_mapped_to_int(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    insert_trace(db, _trace(trace_id="e1", status="error"))
    assert get_trace(db, "e1")["status"] == STATUS_ERROR


def test_list_traces_ordered_by_created_desc(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    insert_trace(db, _trace(trace_id="old", created_at="2026-08-01T00:00:00+00:00"))
    insert_trace(db, _trace(trace_id="new", created_at="2026-08-12T00:00:00+00:00"))
    ids = [r["id"] for r in list_traces(db)]
    assert ids == ["new", "old"]


def test_list_traces_status_filter(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    insert_trace(db, _trace(trace_id="ok", status="success"))
    insert_trace(db, _trace(trace_id="bad", status="error"))
    ids = [r["id"] for r in list_traces(db, status=STATUS_ERROR)]
    assert ids == ["bad"]


def test_experiment_id_stored(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    insert_trace(db, _trace(trace_id="exp"), experiment_id="test1")
    insert_trace(db, _trace(trace_id="plain"))
    assert get_trace(db, "exp")["experiment_id"] == "test1"
    assert get_trace(db, "plain")["experiment_id"] is None


def test_get_trace_missing_returns_none(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    assert get_trace(db, "nope") is None
