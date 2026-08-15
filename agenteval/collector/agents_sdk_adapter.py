"""OpenAI Agents SDK 采集适配器。

把 SDK 的 TracingProcessor 事件（trace/span start/end）映射为框架无关的
span 事件流，复用 SpanCollector + serializer + storage，生成与 LangGraph
同构的 trace JSON，Web / 诊断 / replay 开箱即用。

依赖 openai-agents（可选 extra：agenteval-debugger[agents-sdk]）。
本模块只在 agenteval.init(agents_sdk=True) 时被导入，基础安装不引入依赖。
SDK 的 TracingProcessor 回调本身是同步的（在 async 运行循环里被调用），
因此这里不需要 asyncio 桥接：同步采集 + trace 结束时同步写 SQLite。

SDK 0.21 实测的 Runner.run() span 结构（task -> agent -> turn -> response），
适配规则：
- task / turn 是结构包装，不生成 collector span；子节点挂到最近保留祖先；
- 第一个 agent span 提升为根（agent_run），嵌套 agent（handoff）保持 node；
- response span 才是真正的 LLM 调用，映射为 llm_call，模型名作为 span 名。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agents.tracing import TracingProcessor

from .core import SpanCollector, safe_call
from .types import cap_messages, to_json_safe, truncate_field

logger = logging.getLogger("agenteval.agents_sdk")

# SDK span type -> 我们的 span type
_SDK_SPAN_TYPES: dict[str, str] = {
    "agent": "agent_run",
    "function": "tool_call",
    "generation": "llm_call",
    "response": "llm_call",
    "custom": "node",
    "guardrail": "node",
    "handoff": "node",
    "mcp_tools": "tool_call",
    "speech": "node",
    "transcription": "node",
}

# 结构包装 span：不产生 collector span，子节点挂到最近保留祖先。
_STRUCTURAL_TYPES = {"task", "turn"}

# OpenAI 消息 role -> agenteval message type（replay 依赖 type 字段重建消息）
_ROLE_TO_MESSAGE_TYPE = {
    "system": "system",
    "user": "human",
    "assistant": "ai",
    "tool": "tool",
}


class AgentEvalTracingProcessor(TracingProcessor):
    """把 OpenAI Agents SDK 的 trace 事件收集为 agenteval trace 并持久化。"""

    def __init__(
        self,
        persist: Callable[[dict[str, Any]], None],
        *,
        agent_name: str | None = None,
    ) -> None:
        self._persist = persist
        self._agent_name = agent_name
        # trace_id -> collector：SDK 允许多个 trace 交错执行，按 trace 隔离。
        self._collectors: dict[str, SpanCollector] = {}
        # trace_id -> span_id -> 最近保留祖先 span_id（None 表示根）
        self._anchors: dict[str, dict[str, str | None]] = {}

    def on_trace_start(self, trace: Any) -> None:
        name = self._agent_name or getattr(trace, "name", None) or "OpenAI Agent"
        collector = SpanCollector(agent_name=name)
        collector.framework = "openai_agents"
        self._collectors[trace.trace_id] = collector

    def on_span_start(self, span: Any) -> None:
        def _run() -> None:
            collector = self._collectors.get(span.trace_id)
            if collector is None:
                # 防御：span 事件先于 trace_start 到达时补建 collector。
                collector = SpanCollector(agent_name="OpenAI Agent")
                collector.framework = "openai_agents"
                self._collectors[span.trace_id] = collector
            anchors = self._anchors.setdefault(span.trace_id, {})
            anchor = anchors.get(span.parent_id)
            if span.span_data.type in _STRUCTURAL_TYPES:
                anchors[span.span_id] = anchor
                return
            span_type = _span_type(span, anchor)
            if span_type == "agent_run":
                # 首个 agent span 成为根：忽略 task 包装父节点。
                anchor = None
                if self._agent_name is None:
                    collector.agent_name = _span_name(span) or collector.agent_name
            anchors[span.span_id] = span.span_id
            collector.start_span(
                span.span_id,
                anchor,
                span_type,
                _span_name(span),
                truncate_field(_span_input(span)),
                metadata=_span_metadata(span),
                started_at=span.started_at,
            )

        safe_call(_run, logger)

    def on_span_end(self, span: Any) -> None:
        def _run() -> None:
            if span.span_data.type in _STRUCTURAL_TYPES:
                return
            collector = self._collectors.get(span.trace_id)
            if collector is None:
                return
            error = getattr(span, "error", None)
            if error:
                message = error.get("message") if isinstance(error, dict) else str(error)
                collector.error_span(
                    span.span_id, message or error, ended_at=span.ended_at
                )
                return
            sdk_type = span.span_data.type
            if sdk_type in ("generation", "response"):
                # model / usage / output 在 span 结束时才填充，必须在这里捕获。
                end_meta = _llm_end_metadata(span)
                model = end_meta.get("model_version")
                if model:
                    collector.rename_span(span.span_id, model)
                collector.end_span(
                    span.span_id,
                    truncate_field(_span_output(span)),
                    ended_at=span.ended_at,
                    metadata=end_meta,
                )
            else:
                collector.end_span(
                    span.span_id,
                    truncate_field(_span_output(span)),
                    ended_at=span.ended_at,
                )

        safe_call(_run, logger)

    def on_trace_end(self, trace: Any) -> None:
        def _run() -> None:
            collector = self._collectors.pop(trace.trace_id, None)
            self._anchors.pop(trace.trace_id, None)
            if collector is None:
                return
            trace_dict = collector.get_trace()
            _enrich_root_io(trace_dict)
            self._persist(trace_dict)

        safe_call(_run, logger)

    def shutdown(self) -> None:
        self._collectors.clear()
        self._anchors.clear()

    def force_flush(self) -> None:
        pass


def _span_type(span: Any, effective_parent: str | None) -> str:
    sdk_type = getattr(span.span_data, "type", "custom")
    span_type = _SDK_SPAN_TYPES.get(sdk_type, "node")
    # 嵌套 agent（handoff 子代理）按 node 处理，保持"根 agent_run + 中间 node"的树语义。
    if sdk_type == "agent" and effective_parent is not None:
        return "node"
    return span_type


def _span_name(span: Any) -> str:
    data = span.span_data
    sdk_type = getattr(data, "type", None)
    # LLM 调用 span 用模型名命名（与 LangGraph 的 llm_call.name 一致）。
    if sdk_type == "response":
        response = getattr(data, "response", None)
        model = getattr(response, "model", None) if response is not None else None
        if model:
            return str(model)
    if sdk_type == "generation":
        model = getattr(data, "model", None)
        if model:
            return str(model)
    name = getattr(data, "name", None)
    return name if name else getattr(data, "type", "unknown")


def _span_input(span: Any) -> Any:
    data = span.span_data
    sdk_type = getattr(data, "type", None)
    if sdk_type in ("generation", "response"):
        messages = _response_input_messages(getattr(data, "input", None))
        if messages:
            return {"messages": cap_messages(messages)}
        return None
    if sdk_type == "function":
        return getattr(data, "input", None)
    return None


def _span_output(span: Any) -> Any:
    data = span.span_data
    sdk_type = getattr(data, "type", None)
    if sdk_type == "response":
        response = getattr(data, "response", None)
        if response is not None:
            # response.text 是格式配置对象；正文在 output_text。
            text = getattr(response, "output_text", None)
            if not isinstance(text, str):
                raw = getattr(response, "text", None)
                text = raw if isinstance(raw, str) else None
            return {"text": text} if text else None
        return None
    if sdk_type == "generation":
        messages = getattr(data, "output", None)
        if messages:
            return {"messages": [_message_to_agenteval(m) for m in messages]}
        return None
    if sdk_type == "function":
        return getattr(data, "output", None)
    return None


def _response_input_messages(raw: Any) -> list[dict[str, Any]]:
    """把 response span 的 input（str 或 items 列表）转成 agenteval 消息列表。"""
    if isinstance(raw, str):
        return [{"type": "human", "content": raw}] if raw else []
    if not isinstance(raw, list):
        return []
    messages = []
    for item in raw:
        message = _message_to_agenteval(item)
        if message is not None:
            messages.append(message)
    return messages


def _message_to_agenteval(message: Any) -> dict[str, Any] | None:
    """把 OpenAI 格式消息（role/content，content 可能是 parts 列表）归一化。"""
    if isinstance(message, dict):
        role = message.get("role") or message.get("type")
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content")
                    if text:
                        parts.append(str(text))
                elif part is not None:
                    parts.append(str(part))
            content = "\n".join(parts) if parts else None
        return {
            "type": _ROLE_TO_MESSAGE_TYPE.get(str(role), str(role or "human")),
            "content": content,
        }
    if isinstance(message, str):
        return {"type": "human", "content": message}
    return to_json_safe(message)


def _span_metadata(span: Any) -> dict[str, Any]:
    """start 时捕获的基础 metadata（LLM 详情在结束时补）。"""
    data = span.span_data
    sdk_type = getattr(data, "type", None)
    meta: dict[str, Any] = {"sdk_span_type": sdk_type}
    if sdk_type == "generation":
        model = getattr(data, "model", None)
        model_config = getattr(data, "model_config", None)
        if model:
            meta["model_name"] = model
            meta["model_version"] = model
        if isinstance(model_config, dict):
            meta["invocation_params"] = to_json_safe(model_config)
    elif sdk_type == "function":
        mcp = getattr(data, "mcp_data", None)
        if mcp:
            meta["mcp_data"] = to_json_safe(mcp)
    return meta


def _llm_end_metadata(span: Any) -> dict[str, Any]:
    """end 时从 span 提取 model / token_usage / invocation_params。"""
    data = span.span_data
    sdk_type = getattr(data, "type", None)
    if sdk_type == "response":
        response = getattr(data, "response", None)
        model = getattr(response, "model", None) if response is not None else None
        usage = getattr(data, "usage", None) or {}
    elif sdk_type == "generation":
        model = getattr(data, "model", None)
        usage = getattr(data, "usage", None) or {}
    else:
        return {}
    meta: dict[str, Any] = {}
    if model:
        meta["model_name"] = str(model)
        meta["model_version"] = str(model)
    token_usage = {
        "prompt_tokens": usage.get("input_tokens"),
        "completion_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
    token_usage = {k: v for k, v in token_usage.items() if v is not None}
    if token_usage:
        meta["token_usage"] = token_usage
    if sdk_type == "generation":
        model_config = getattr(data, "model_config", None)
        if isinstance(model_config, dict):
            meta["invocation_params"] = to_json_safe(model_config)
    return meta


def _enrich_root_io(trace: dict[str, Any]) -> None:
    """SDK 的 agent span 不带 input/output：用首个 llm 输入/末个 llm 输出补齐。

    这样 Web 列表的"对话内容"预览、详情摘要对 SDK trace 也可用。
    """
    root = trace.get("root_span")
    if not root:
        return
    llm_spans = _walk_llm_spans(root)
    if not llm_spans:
        return
    if root.get("input") is None:
        root["input"] = llm_spans[0].get("input")
    if root.get("output") is None:
        root["output"] = llm_spans[-1].get("output")


def _walk_llm_spans(span: dict[str, Any]) -> list[dict[str, Any]]:
    found = [span] if span.get("type") == "llm_call" else []
    for child in span.get("children", []):
        found.extend(_walk_llm_spans(child))
    return found
