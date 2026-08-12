"""存储层表结构定义与 status 常量映射。"""

STATUS_SUCCESS = 0
STATUS_ERROR = 1
STATUS_RUNNING = 2

STATUS_LABELS = {0: "success", 1: "error", 2: "running"}

# 严格按设计文档定义；加 IF NOT EXISTS 使 init_db 幂等。
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    status INTEGER,          -- 0=success, 1=error, 2=running
    framework TEXT,
    agent_name TEXT,
    trace_json JSON,         -- SQLite 3.9+ JSON1，支持 json_extract() 路径查询
    experiment_id TEXT       -- V2 方案对比预留
);

CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_experiment ON traces(experiment_id);
"""
