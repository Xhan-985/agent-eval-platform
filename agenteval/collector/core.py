"""框架无关的 span 事件采集器。

LangGraph callback 与 OpenAI Agents SDK 适配器共用同一个扁平状态机：
维护 span 状态 + 父子关系，最终由 serializer 组装成嵌套 trace JSON。
这样新增框架只需要把框架事件映射成 start/end/error 三个方法调用。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .types import MAX_ERROR_CHARS, SpanState, to_json_safe, truncate_field

logger = logging.getLogger("agenteval.collector.core")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def safe_call(fn: Callable[[], None], logger_: logging.Logger = logger) -> None:
    """内部异常一律捕获记录，不影响 Agent 执行。"""
    try:
        fn()
    except Exception:
        logger_.exception("采集器内部异常（已忽略，不影响 Agent 执行）")


class SpanCollector:
    """扁平 span 状态机：start/end/error 事件 → 状态 + 父子关系。"""

    def __init__(self, agent_name: str | None = None) -> None:
        self.agent_name = agent_name
        # 框架标识：serializer 写入 trace.framework；SDK 适配器会覆盖。
        self.framework: str = "langgraph"
        self.reset()

    def reset(self) -> None:
        self._states: dict[str, SpanState] = {}
        self._children: dict[str, list[str]] = {}
        self._root_run_id: str | None = None

    def get_trace(self) -> dict[str, Any]:
        from .serializer import build_trace  # 延迟导入避免循环依赖

        return build_trace(self)

    def start_span(
        self,
        span_id: Any,
        parent_id: Any,
        span_type: str,
        name: str,
        input_: Any,
        metadata: dict[str, Any] | None = None,
        started_at: str | None = None,
    ) -> None:
        """开始一个 span。parent_id 为 None 且尚无根时记为根 span。"""
        sid = str(span_id)
        pid = str(parent_id) if parent_id else None
        if pid is None:
            if self._root_run_id is None:
                self._root_run_id = sid
        else:
            self._children.setdefault(pid, []).append(sid)
        self._states[sid] = SpanState(
            span_id=sid,
            parent_id=pid,
            type=span_type,
            name=name,
            input=input_,
            output=None,
            error=None,
            started_at=started_at or now_iso(),
            ended_at=None,
            metadata=dict(metadata or {}),
        )

    def ensure_state(self, span_id: Any, parent_id: Any = None) -> SpanState:
        """取 span 状态；若只有 end/error 事件，先补一个占位 span。"""
        sid = str(span_id)
        if sid not in self._states:
            self.start_span(sid, parent_id, "node", "unknown", None)
        return self._states[sid]

    def end_span(
        self,
        span_id: Any,
        output: Any,
        ended_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        state = self.ensure_state(span_id)
        state["output"] = truncate_field(to_json_safe(output))
        state["ended_at"] = ended_at or now_iso()
        if metadata:
            state["metadata"].update({k: v for k, v in metadata.items() if v is not None})

    def rename_span(self, span_id: Any, name: str) -> None:
        """给已存在的 span 改名（SDK 的 LLM span 名称结束时才确定）。"""
        if name:
            self.ensure_state(span_id)["name"] = name

    def error_span(
        self,
        span_id: Any,
        error: Any,
        parent_id: Any = None,
        ended_at: str | None = None,
    ) -> None:
        state = self.ensure_state(span_id, parent_id)
        state["error"] = str(error)[:MAX_ERROR_CHARS]
        state["ended_at"] = ended_at or now_iso()
