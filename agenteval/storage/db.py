"""SQLite CRUD：初始化、插入 trace、列表查询、详情查询。"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from agenteval.collector.metrics import (
    aggregate_total_tokens,
    count_spans,
    extract_query_preview,
    trace_duration_ms,
)

from .schema import ADDITIVE_COLUMNS, SCHEMA_SQL, SCHEMA_VERSION, STATUS_LABELS, STATUS_SUCCESS

logger = logging.getLogger("agenteval.storage")

# 公共基础列 + 冗余汇总列；详情/插入额外含 trace_json。列表查询不含 trace_json 以免全量解析。
# 列顺序必须与 insert_trace 的参数元组一致（trace_json 在 experiment_id 前）。
_LIST_COLUMNS = (
    "id, created_at, status, framework, agent_name, experiment_id, "
    "total_tokens, duration_ms, span_count, query_preview"
)
_DETAIL_COLUMNS = (
    "id, created_at, status, framework, agent_name, trace_json, experiment_id, "
    "total_tokens, duration_ms, span_count, query_preview"
)
_INSERT_COLUMNS = _DETAIL_COLUMNS


def _connect(db_path: str) -> sqlite3.Connection:
    """打开连接并设置并发安全参数（WAL + busy_timeout）。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path: str) -> None:
    """创建数据库文件、traces 表与索引（幂等），并对旧库补齐增量列与汇总值。"""
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        _backfill_summary(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """对已存在的旧库补齐增量列（v1 → v2）。新库由 SCHEMA_SQL 直接建全列。"""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(traces)")}
    for col, ddl in ADDITIVE_COLUMNS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE traces {ddl}")
            logger.info("迁移：traces 表新增列 %s", col)


def _backfill_summary(conn: sqlite3.Connection) -> None:
    """为迁移前已存在的行回填汇总列（一次性，幂等）。

    total_tokens 为 NULL 视为 v2 未回填；query_preview 为 NULL 视为 v3 未回填。
    """
    rows = conn.execute(
        "SELECT id, trace_json FROM traces WHERE total_tokens IS NULL OR query_preview IS NULL"
    ).fetchall()
    for row in rows:
        trace_json = row["trace_json"]
        if not trace_json:
            continue
        conn.execute(
            "UPDATE traces SET total_tokens = ?, duration_ms = ?, span_count = ?, "
            "query_preview = ? WHERE id = ?",
            (
                aggregate_total_tokens(trace_json),
                trace_duration_ms(trace_json),
                count_spans(trace_json),
                extract_query_preview(trace_json),
                row["id"],
            ),
        )


def insert_trace(
    db_path: str, trace: dict[str, Any], experiment_id: str | None = None
) -> None:
    """把一条 trace 写入数据库。

    插入时一次性计算 total_tokens / duration_ms / span_count / query_preview
    冗余汇总列，使后续列表/仪表盘查询无需解析 trace_json。trace_id 为新 UUID，不会真正触发替换。
    """
    status = _status_to_int(trace.get("status", "success"))
    trace_json_str = json.dumps(trace, ensure_ascii=False)
    total_tokens = aggregate_total_tokens(trace)
    duration_ms = trace_duration_ms(trace)
    span_count = count_spans(trace)
    query_preview = extract_query_preview(trace)
    conn = _connect(db_path)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO traces ({_INSERT_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace["trace_id"],
                trace.get("created_at"),
                status,
                trace.get("framework"),
                trace.get("agent_name"),
                trace_json_str,
                experiment_id,
                total_tokens,
                duration_ms,
                span_count,
                query_preview,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_traces(db_path: str, status: int | None = None) -> list[dict[str, Any]]:
    """按创建时间倒序返回 trace 行（不含 trace_json，列表/仪表盘用）；status 可选过滤。"""
    conn = _connect(db_path)
    try:
        if status is None:
            sql = f"SELECT {_LIST_COLUMNS} FROM traces ORDER BY created_at DESC"
            rows = conn.execute(sql)
        else:
            sql = (
                f"SELECT {_LIST_COLUMNS} FROM traces "
                "WHERE status = ? ORDER BY created_at DESC"
            )
            rows = conn.execute(sql, (status,))
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_trace(db_path: str, trace_id: str) -> dict[str, Any] | None:
    """按 id 查询单条 trace（含完整 trace_json），不存在返回 None。"""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            f"SELECT {_DETAIL_COLUMNS} FROM traces WHERE id = ?", (trace_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _status_to_int(status: str) -> int:
    label_to_code = {label: code for code, label in STATUS_LABELS.items()}
    return label_to_code.get(status, STATUS_SUCCESS)
