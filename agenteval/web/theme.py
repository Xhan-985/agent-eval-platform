"""前端统一的视觉令牌：span 类型配色、状态徽标、类型标签/图标。

集中定义后供 list_view / trace_view / timeline_view / dashboard_view 复用，
避免各页面散落硬编码颜色与 emoji。颜色采用 hex，便于注入 graphviz DOT
与 plotly/altair 图表。
"""

from __future__ import annotations

# span 类型主色（与 .streamlit/config.toml 主色呼应）
SPAN_COLORS: dict[str, str] = {
    "agent_run": "#6366f1",  # indigo
    "node": "#0ea5e9",       # sky
    "llm_call": "#22c55e",   # green
    "tool_call": "#f59e0b",  # amber
}

ERROR_COLOR = "#ef4444"  # red-500：出错 span 统一标红

# graphviz 节点填充色（浅化版本，保证文字可读）
SPAN_FILLS: dict[str, str] = {
    "agent_run": "#e0e7ff",
    "node": "#e0f2fe",
    "llm_call": "#dcfce7",
    "tool_call": "#fef3c7",
}
ERROR_FILL = "#fee2e2"

# 类型标签（中文，用于徽标/表头）
TYPE_LABELS: dict[str, str] = {
    "agent_run": "Agent",
    "node": "节点",
    "llm_call": "LLM",
    "tool_call": "工具",
}

# 类型图标（graphviz DOT 节点用，保留 emoji 以兼容 build_dot 既有测试）
TYPE_ICONS: dict[str, str] = {
    "agent_run": "🤖",
    "node": "📦",
    "llm_call": "🔵",
    "tool_call": "🔧",
}
ERROR_ICON = "❌"
UNKNOWN_ICON = "❓"

# 状态徽标：(文案, 颜色)
STATUS_BADGES: dict[str, tuple[str, str]] = {
    "success": ("成功", "#16a34a"),
    "error": ("失败", "#dc2626"),
    "running": ("运行中", "#2563eb"),
    "unknown": ("未知", "#64748b"),
}

# 状态 emoji：用于 React 安全的原生徽标（不依赖 unsafe_allow_html）
STATUS_EMOJI: dict[str, str] = {
    "success": "✅",
    "error": "❌",
    "running": "⏳",
    "unknown": "❓",
}


def span_color(span_type: str) -> str:
    return SPAN_COLORS.get(span_type, "#64748b")


def span_fill(span_type: str) -> str:
    return SPAN_FILLS.get(span_type, "#f1f5f9")


def type_label(span_type: str) -> str:
    return TYPE_LABELS.get(span_type, span_type or "未知")


def type_icon(span_type: str, has_error: bool = False) -> str:
    if has_error:
        return ERROR_ICON
    return TYPE_ICONS.get(span_type, UNKNOWN_ICON)


def status_badge(status: str) -> tuple[str, str]:
    return STATUS_BADGES.get(status or "unknown", STATUS_BADGES["unknown"])


def status_emoji(status: str) -> str:
    return STATUS_EMOJI.get(status or "unknown", STATUS_EMOJI["unknown"])
