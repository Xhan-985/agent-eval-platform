"""存储层表结构定义与 status 常量映射。"""

STATUS_SUCCESS = 0
STATUS_ERROR = 1
STATUS_RUNNING = 2

STATUS_LABELS = {0: "success", 1: "error", 2: "running"}

# schema 版本：v1 初始表；v2 新增 total_tokens/duration_ms/span_count 冗余汇总列；
# v3 新增 query_preview 列（首条用户输入预览，列表/仪表盘据此区分各 trace）。
# init_db 会在建表后跑 _migrate 补列，旧库无需重建即可升级。
SCHEMA_VERSION = 3

# 严格按设计文档定义；加 IF NOT EXISTS 使 init_db 幂等。
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    status INTEGER,          -- 0=success, 1=error, 2=running
    framework TEXT,
    agent_name TEXT,
    trace_json JSON,         -- SQLite 3.9+ JSON1，支持 json_extract() 路径查询
    experiment_id TEXT,      -- V2 方案对比预留
    total_tokens INTEGER,    -- 冗余汇总：整 trace token 总数（插入时算好，列表免解析）
    duration_ms INTEGER,     -- 冗余汇总：root_span 总耗时毫秒
    span_count INTEGER,      -- 冗余汇总：span 总数
    query_preview TEXT       -- 冗余汇总：首条用户输入预览（列表/仪表盘识别用）
);

CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_experiment ON traces(experiment_id);
"""

# 旧库（v1）补列用的增量 DDL。ADD COLUMN 不支持 IF NOT EXISTS，
# 靠 init_db 先查 table_info 去重。列名 → DDL 片段。
ADDITIVE_COLUMNS = {
    "total_tokens": "ADD COLUMN total_tokens INTEGER",
    "duration_ms": "ADD COLUMN duration_ms INTEGER",
    "span_count": "ADD COLUMN span_count INTEGER",
    "query_preview": "ADD COLUMN query_preview TEXT",
}
