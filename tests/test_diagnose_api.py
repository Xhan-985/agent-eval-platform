"""agenteval.diagnose() 对外 API 的测试（含 dogfooding 入库）。"""

from langchain_core.messages import AIMessage

import agenteval
from agenteval.diagnose.report import has_complete_report
from agenteval.storage.db import init_db, insert_trace, list_traces

REPORT = (
    "## 概述\n执行整体正常。\n\n"
    "## 可疑步骤\n- s-tool 需要关注。\n\n"
    "## 原因分析\n工具返回了脏数据。\n\n"
    "## 修改建议\n给工具调用加异常处理。"
)


class _ScriptedLLM:
    """按脚本依次返回 AIMessage 的假 LLM（bind_tools 契约）。"""

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)

    def bind_tools(self, specs):
        return self

    def invoke(self, messages):
        response = self.responses.pop(0)
        if isinstance(response, AIMessage):
            return response
        return AIMessage(content=response)


def _trace(trace_id: str = "t1") -> dict:
    return {
        "trace_id": trace_id,
        "created_at": "2026-08-15T00:00:00+00:00",
        "status": "error",
        "framework": "langgraph",
        "agent_name": "ReAct Agent",
        "root_span": {
            "span_id": "s-root",
            "type": "agent_run",
            "name": "ReAct Agent",
            "input": {"query": "LangGraph 是什么？"},
            "output": {},
            "error": None,
            "annotation": "这是 Agent 的一次完整执行。",
            "started_at": "2026-08-15T00:00:00+00:00",
            "ended_at": "2026-08-15T00:00:05+00:00",
            "metadata": {},
            "children": [
                {
                    "span_id": "s-tool",
                    "type": "tool_call",
                    "name": "search",
                    "input": {"query": "LangGraph"},
                    "output": {"text": "out"},
                    "error": "boom",
                    "annotation": "Agent 调用了搜索工具",
                    "started_at": "2026-08-15T00:00:01+00:00",
                    "ended_at": "2026-08-15T00:00:02+00:00",
                    "metadata": {},
                    "children": [],
                }
            ],
        },
    }


def test_diagnose_api_records_dogfood_trace(tmp_path):
    db = str(tmp_path / "api.db")
    agenteval.init(db_path=db, llm_factory=lambda name: _ScriptedLLM([REPORT]))
    init_db(db)
    insert_trace(db, _trace("t1"))

    report = agenteval.diagnose("t1")

    assert has_complete_report(report)
    agents = {row["agent_name"] for row in list_traces(db)}
    assert "AgentEval 诊断助手" in agents


def test_diagnose_api_uses_module_factory(tmp_path):
    db = str(tmp_path / "api.db")
    created = []

    def factory(model_name):
        created.append(model_name)
        return _ScriptedLLM([REPORT])

    agenteval.init(db_path=db, llm_factory=factory)
    init_db(db)
    insert_trace(db, _trace("t1"))

    report = agenteval.diagnose("t1", model_name="deepseek-v4-flash")

    assert created == ["deepseek-v4-flash"]
    assert has_complete_report(report)


def test_diagnose_api_without_factory_returns_clear_error(tmp_path):
    db = str(tmp_path / "api.db")
    agenteval.init(db_path=db)
    init_db(db)
    insert_trace(db, _trace("t1"))

    report = agenteval.diagnose("t1")

    assert "未配置 llm_factory" in report


def test_diagnose_api_missing_trace_returns_clear_error(tmp_path):
    db = str(tmp_path / "api.db")
    agenteval.init(db_path=db, llm_factory=lambda name: _ScriptedLLM([REPORT]))
    init_db(db)

    report = agenteval.diagnose("nope")

    assert "trace 不存在" in report
