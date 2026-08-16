"""一键演示数据（agenteval.demo / cli.demo）的单元测试。"""

import agenteval
from agenteval.demo import generate_demo_traces
from agenteval.storage.db import list_traces


def test_generate_demo_traces_creates_three(tmp_path):
    db = str(tmp_path / "demo.db")
    old_db = agenteval._db_path
    try:
        summary = generate_demo_traces(db)
    finally:
        agenteval._db_path = old_db

    assert len(summary) == 3
    assert summary[0]["status"] == "success"  # 正常调用
    assert summary[1]["status"] == "error"  # tool 抛异常 → error trace
    assert summary[2]["status"] == "success"  # 多轮调用

    rows = list_traces(db)
    assert len(rows) == 3
    ids = {r["id"] for r in rows}
    assert {item["trace_id"] for item in summary} == ids


def test_generate_demo_traces_labels(tmp_path):
    db = str(tmp_path / "demo.db")
    old_db = agenteval._db_path
    try:
        summary = generate_demo_traces(db)
    finally:
        agenteval._db_path = old_db

    labels = [item["label"] for item in summary]
    assert "场景 1：正常调用" in labels
    assert "场景 2：tool 抛异常" in labels
    assert "场景 3：多轮调用" in labels
