"""存储层表结构与状态常量的单元测试。"""

from agenteval.storage.schema import (
    SCHEMA_SQL,
    STATUS_ERROR,
    STATUS_LABELS,
    STATUS_RUNNING,
    STATUS_SUCCESS,
)


def test_status_constants_match_design():
    assert STATUS_SUCCESS == 0
    assert STATUS_ERROR == 1
    assert STATUS_RUNNING == 2
    assert STATUS_LABELS == {0: "success", 1: "error", 2: "running"}


def test_schema_defines_traces_table():
    assert "CREATE TABLE" in SCHEMA_SQL
    assert "traces" in SCHEMA_SQL
    assert "id TEXT PRIMARY KEY" in SCHEMA_SQL
    assert "created_at TIMESTAMP" in SCHEMA_SQL
    assert "status INTEGER" in SCHEMA_SQL
    assert "framework TEXT" in SCHEMA_SQL
    assert "agent_name TEXT" in SCHEMA_SQL
    assert "trace_json JSON" in SCHEMA_SQL
    assert "experiment_id TEXT" in SCHEMA_SQL


def test_schema_defines_indexes():
    assert "idx_traces_created" in SCHEMA_SQL
    assert "idx_traces_status" in SCHEMA_SQL
    assert "idx_traces_experiment" in SCHEMA_SQL
