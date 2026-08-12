"""SQLite CRUD：初始化、插入 trace、列表查询、详情查询。"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from .schema import SCHEMA_SQL, STATUS_LABELS, STATUS_SUCCESS

SCHEMA_VERSION = 1
_COLUMNS = "id, created_at, status, framework, agent_name, trace_json, experiment_id"

logger = logging.getLogger("agenteval.storage")


def _connect(db_path: str) -> sqlite3.Connection:
    """打开连接并设置并发安全参数（WAL + busy_timeout）。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path: str) -> None:
    """创建数据库文件、traces 表与索引（幂等）。"""
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def insert_trace(
    db_path: str, trace: dict[str, Any], experiment_id: str | None = None
) -> None:
    """把一条 trace 写入数据库（同 id 覆盖）。"""
    status = _status_to_int(trace.get("status", "success"))
    conn = _connect(db_path)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO traces ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                trace["trace_id"],
                trace.get("created_at"),
                status,
                trace.get("framework"),
                trace.get("agent_name"),
                json.dumps(trace, ensure_ascii=False),
                experiment_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_traces(db_path: str, status: int | None = None) -> list[dict[str, Any]]:
    """按创建时间倒序返回 trace 行；status 不为 None 时按状态过滤。"""
    conn = _connect(db_path)
    try:
        if status is None:
            sql = f"SELECT {_COLUMNS} FROM traces ORDER BY created_at DESC"
            rows = conn.execute(sql)
        else:
            sql = (
                f"SELECT {_COLUMNS} FROM traces "
                "WHERE status = ? ORDER BY created_at DESC"
            )
            rows = conn.execute(sql, (status,))
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_trace(db_path: str, trace_id: str) -> dict[str, Any] | None:
    """按 id 查询单条 trace，不存在返回 None。"""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM traces WHERE id = ?", (trace_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _status_to_int(status: str) -> int:
    label_to_code = {label: code for code, label in STATUS_LABELS.items()}
    return label_to_code.get(status, STATUS_SUCCESS)
