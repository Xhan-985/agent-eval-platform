"""LangGraph/LangChain callback 采集器（SpanCollector 的薄适配层）。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from .core import SpanCollector, now_iso, safe_call
from .types import SpanState, cap_messages, to_json_safe, truncate_field

logger = logging.getLogger("agenteval.collector")


def _extract_model_version(llm_output, invocation_params) -> str | None:
    """从 llm_output 或 invocation_params 提取 model_version（.get() 兜底）。

    不同模型返回结构不同：优先取 model_version/version 字段，
    取不到时回退到 invocation_params 的 model id（如 deepseek-v4-flash）。
    """
    for source in (llm_output, invocation_params):
        if not isinstance(source, dict):
            continue
        for key in ("model_version", "version"):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
    if isinstance(invocation_params, dict):
        model = invocation_params.get("model")
        if isinstance(model, str) and model:
            return model
    return None


class AgentEvalCallbackHandler(BaseCallbackHandler):
    """接收 LangGraph 执行事件，维护扁平 span 状态与父子关系。

    只负责采集，不负责组装；trace 树构建由 serializer 完成。
    callback 内部异常一律捕获记录，不影响 Agent 执行。
    """

    def __init__(self, verbose: bool = False) -> None:
        super().__init__()
        self._verbose = verbose
        self._collector = SpanCollector()

    # ------------------------------------------------------------------
    # 兼容旧内部属性：serializer 与既有测试直接读取这些字段。
    # ------------------------------------------------------------------
    @property
    def agent_name(self) -> str | None:
        return self._collector.agent_name

    @agent_name.setter
    def agent_name(self, value: str | None) -> None:
        self._collector.agent_name = value

    @property
    def _states(self) -> dict[str, SpanState]:
        return self._collector._states

    @property
    def _children(self) -> dict[str, list[str]]:
        return self._collector._children

    @property
    def _root_run_id(self) -> str | None:
        return self._collector._root_run_id

    def reset(self) -> None:
        """重置采集状态，准备下一次执行。"""
        self._collector.reset()

    def get_trace(self) -> dict[str, Any]:
        """返回采集到的完整 trace（Agent 执行结束后调用）。"""
        return self._collector.get_trace()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _safe(self, fn: Callable[[], None]) -> None:
        safe_call(fn, logger)

    def _start_span(
        self,
        run_id,
        parent_run_id,
        span_type: str,
        name: str,
        input_: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._collector.start_span(
            run_id,
            parent_run_id,
            span_type,
            name,
            input_,
            metadata=metadata,
        )

    def _ensure_state(self, run_id, parent_run_id=None) -> SpanState:
        """取 span 状态；若只有 end/error 事件，先补一个占位 span。"""
        return self._collector.ensure_state(run_id, parent_run_id)

    def _record_error(self, run_id, parent_run_id, error) -> None:
        self._collector.error_span(run_id, error, parent_id=parent_run_id)

    def _record_end(self, run_id, parent_run_id, output) -> None:
        self._collector.end_span(run_id, output)

    def _llm_start(
        self,
        run_id,
        parent_run_id,
        *,
        serialized=None,
        messages=None,
        prompts=None,
        event_meta=None,
        event_kwargs=None,
    ) -> None:
        serialized = serialized or {}
        event_kwargs = event_kwargs or {}
        name = serialized.get("name") or "llm"
        meta = {
            "model_name": name,
            "invocation_params": event_kwargs.get("invocation_params"),
            "options": event_kwargs.get("options"),
            "langgraph_node": (event_meta or {}).get("langgraph_node"),
        }
        if messages is not None:
            flat = [to_json_safe(m) for batch in messages for m in batch]
            input_ = {"messages": cap_messages(flat)}
        elif prompts is not None:
            input_ = {"prompts": prompts}
        else:
            input_ = None
        self._start_span(
            run_id,
            parent_run_id,
            "llm_call",
            name,
            truncate_field(to_json_safe(input_)),
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # chain 事件
    # ------------------------------------------------------------------
    def on_chain_start(
        self,
        serialized,
        inputs,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        **kwargs,
    ) -> None:
        def _run() -> None:
            span_type = "agent_run" if parent_run_id is None else "node"
            name = (
                kwargs.get("name")
                or (metadata or {}).get("langgraph_node")
                or (serialized or {}).get("name")
                or span_type
            )
            extra = {
                "langgraph_node": (metadata or {}).get("langgraph_node"),
                "tags": list(tags) if tags else [],
            }
            self._start_span(
                run_id,
                parent_run_id,
                span_type,
                name,
                truncate_field(to_json_safe(inputs)),
                metadata=extra,
            )

        self._safe(_run)

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs) -> None:
        self._safe(lambda: self._record_end(run_id, parent_run_id, outputs))

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs) -> None:
        self._safe(lambda: self._record_error(run_id, parent_run_id, error))

    # ------------------------------------------------------------------
    # LLM / chat model 事件
    # ------------------------------------------------------------------
    def on_chat_model_start(
        self,
        serialized,
        messages,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        **kwargs,
    ) -> None:
        self._safe(
            lambda: self._llm_start(
                run_id,
                parent_run_id,
                serialized=serialized,
                messages=messages,
                event_meta=metadata,
                event_kwargs=kwargs,
            )
        )

    def on_llm_start(
        self,
        serialized,
        prompts,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        **kwargs,
    ) -> None:
        self._safe(
            lambda: self._llm_start(
                run_id,
                parent_run_id,
                serialized=serialized,
                prompts=prompts,
                event_meta=metadata,
                event_kwargs=kwargs,
            )
        )

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs) -> None:
        def _run() -> None:
            state = self._ensure_state(run_id, parent_run_id)
            output = None
            if response is not None and getattr(response, "generations", None):
                texts = [g.text for g in response.generations[0]]
                output = {"text": texts[0] if len(texts) == 1 else texts}
            state["output"] = truncate_field(to_json_safe(output))
            llm_output = getattr(response, "llm_output", None) if response is not None else None
            if llm_output and llm_output.get("token_usage"):
                state["metadata"].setdefault("token_usage", llm_output["token_usage"])
            model_version = _extract_model_version(
                llm_output, state["metadata"].get("invocation_params")
            )
            if model_version:
                state["metadata"]["model_version"] = model_version
            state["ended_at"] = now_iso()

        self._safe(_run)

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs) -> None:
        self._safe(lambda: self._record_error(run_id, parent_run_id, error))

    # ------------------------------------------------------------------
    # tool 事件
    # ------------------------------------------------------------------
    def on_tool_start(
        self,
        serialized,
        input_str,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        inputs=None,
        **kwargs,
    ) -> None:
        def _run() -> None:
            name = (serialized or {}).get("name") or kwargs.get("name") or "tool"
            meta = {
                "tool_call_id": kwargs.get("tool_call_id"),
                "tags": list(tags) if tags else [],
            }
            raw_input = inputs if inputs is not None else input_str
            self._start_span(
                run_id,
                parent_run_id,
                "tool_call",
                name,
                truncate_field(to_json_safe(raw_input)),
                metadata=meta,
            )

        self._safe(_run)

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs) -> None:
        self._safe(lambda: self._record_end(run_id, parent_run_id, output))

    def on_tool_error(self, error, *, run_id, parent_run_id=None, **kwargs) -> None:
        self._safe(lambda: self._record_error(run_id, parent_run_id, error))
