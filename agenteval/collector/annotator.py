"""教学注释生成器。

纯函数、无副作用：输入 span dict，输出 1-2 句中文注释。
"""

from __future__ import annotations

import json
from typing import Any

from .types import SUMMARY_MAX_CHARS

_GENERIC = "Agent 执行了一步操作"

_NODE_HINTS = {
    "reason": "这一步 Agent 在推理",
    "search": "这一步 Agent 在检索信息",
    "retrieve": "这一步 Agent 在检索信息",
    "tools": "这一步 Agent 在调用工具",
    "tool": "这一步 Agent 在调用工具",
    "final": "这一步 Agent 生成最终回答",
    "respond": "这一步 Agent 生成最终回答",
    "agent": "这一步 Agent 在执行自身逻辑",
}


def annotate(span: dict[str, Any]) -> str:
    """为单个 span 生成教学化中文注释（≤100 字，最多 2 句）。"""
    error = span.get("error")
    if error:
        return _error_annotation(span, str(error))
    span_type = span.get("type", "")
    name = span.get("name") or span_type
    if span_type == "agent_run":
        return f"这是 Agent 的一次完整执行。目标：{extract_question(span.get('input'))}"
    if span_type == "node":
        return f"Agent 进入 {name} 节点。{node_role_hint(name)}"
    if span_type == "llm_call":
        return f"Agent 调用 {name} 决定下一步。{extract_decision(span.get('output'))}"
    if span_type == "tool_call":
        return (
            f"Agent 调用 {name} 工具，参数：{summarize(span.get('input'))}。"
            f"返回：{summarize(span.get('output'))}"
        )
    return _GENERIC


def extract_question(input_: Any, max_chars: int = 30) -> str:
    """从 agent_run 的 input 提取用户问题（最多 30 字）。"""
    if isinstance(input_, dict):
        messages = input_.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                role = message.get("type") if isinstance(message, dict) else None
                if role in ("human", "user"):
                    text = _extract_text(message)
                    if text:
                        return summarize(text, max_chars)
            for message in reversed(messages):
                    text = _extract_text(message)
                    if text:
                        return summarize(text, max_chars)
        for key in ("query", "question", "input", "text"):
            text = _extract_text(input_.get(key))
            if text:
                return summarize(text, max_chars)
    text = _extract_text(input_)
    return summarize(text, max_chars) if text else "未识别"


def node_role_hint(name: str) -> str:
    """根据节点名给出教学化解释。"""
    return f"{_NODE_HINTS.get(name, '执行节点逻辑')}。"


def extract_decision(output: Any) -> str:
    """从 LLM output 提取决策结果。"""
    if isinstance(output, dict):
        tool_calls = output.get("tool_calls")
        if tool_calls:
            names = [tc.get("name") or "工具" for tc in tool_calls if isinstance(tc, dict)]
            if names:
                return f"选择了调用 {names[0]} 工具"
        for key in ("content", "text"):
            content = output.get(key)
            if content:
                return f"输出：{summarize(content)}"
    if output is None:
        return "未产生输出"
    return f"输出：{summarize(output)}"


def summarize(value: Any, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """把任意值摘要成不超过 max_chars 的字符串。"""
    if value is None:
        return "（空）"
    text = _extract_text(value)
    if text is None:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def common_cause_hint(error: str) -> str:
    """根据错误类型给出常见排查方向。"""
    low = error.lower()
    if "timeout" in low or "timed out" in low:
        return "网络或 API 超时，建议检查网络或增加重试"
    if "rate" in low or "429" in low:
        return "触发了限流，建议降低请求频率或稍后重试"
    if "401" in low or "invalid api key" in low or "authentication" in low:
        return "API key 无效或未配置，请检查环境变量"
    if "valueerror" in low or "typeerror" in low:
        return "代码或数据格式问题，建议检查该步骤的输入输出"
    return "具体原因需要结合上下文排查，建议查看该 span 的输入输出"


def _error_annotation(span: dict[str, Any], error: str) -> str:
    name = span.get("name") or span.get("type") or "未知步骤"
    return f"⚠️ {name} 这一步出错了：{error[:200]}。可能原因：{common_cause_hint(error)}"


def _extract_text(value: Any) -> str | None:
    """从消息/字典/列表中尽力提取纯文本。"""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [t for t in (_extract_text(c) for c in content) if t]
            return " ".join(parts) if parts else None
        return None
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and isinstance(value[0], str):
            return _extract_text(value[1])
        parts = [t for t in (_extract_text(v) for v in value) if t]
        return " ".join(parts) if parts else None
    return None
