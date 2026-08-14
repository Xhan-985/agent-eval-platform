"""自绘 SVG 树：不依赖 graphviz/viz.js，箭头确定渲染，LR 布局。

用纯 Python 生成 SVG 字符串，经 st.components.v1.html 嵌入页面，
规避 Streamlit graphviz_chart 在浏览器端（viz.js）LR 布局下重绘丢箭头的问题。
纯函数 build_svg 便于单元测试。
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

import streamlit as st

from agenteval.web.metrics import format_duration
from agenteval.web.theme import (
    ERROR_COLOR,
    ERROR_FILL,
    ERROR_ICON,
    SPAN_COLORS,
    SPAN_FILLS,
    TYPE_ICONS,
    UNKNOWN_ICON,
)

NODE_W = 200
NODE_H = 46
COL_W = 235
ROW_H = 58
MARGIN = 16
_FONT_FAMILY = "'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif"


def build_svg(trace: dict[str, Any]) -> str:
    """把 trace 树转成 LR 布局的 SVG 字符串（纯函数）。"""
    rows, edges, width, height = _layout(trace)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" font-family="{_FONT_FAMILY}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#94a3b8"/></marker></defs>',
    ]
    for (x1, y1), (x2, y2) in edges:
        parts.append(
            f'<path d="M {x1 + NODE_W} {y1 + NODE_H / 2:.0f} '
            f'L {x2} {y2 + NODE_H / 2:.0f}" stroke="#94a3b8" stroke-width="1.5" '
            'marker-end="url(#arrow)" fill="none"/>'
        )
    for span, depth, pos in rows:
        parts.append(_node_svg(span, depth, pos))
    parts.append("</svg>")
    return "\n".join(parts)


def render_svg(trace: dict[str, Any]) -> None:
    """在详情页渲染 SVG 树（iframe 嵌入，高度超出时可滚动）。"""
    rows, _edges, _width, height = _layout(trace)
    if not rows:
        st.caption("暂无树数据")
        return
    st.components.v1.html(
        build_svg(trace), height=min(int(height) + 8, 1000), scrolling=True
    )


def _layout(trace: dict[str, Any]):
    """DFS 展平：返回 (rows, edges, width, height)。rows 为 (span, depth, pos)。"""
    root = trace.get("root_span")
    if not root:
        return [], [], 0, 0
    rows: list[tuple[dict[str, Any], int, int]] = []
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    pos = 0

    def walk(span: dict[str, Any], depth: int, parent_xy) -> None:
        nonlocal pos
        x = MARGIN + depth * COL_W
        y = MARGIN + pos * ROW_H
        rows.append((span, depth, pos))
        pos += 1
        if parent_xy is not None:
            edges.append((parent_xy, (x, y)))
        for child in span.get("children", []):
            walk(child, depth + 1, (x, y))

    walk(root, 0, None)
    max_depth = max(depth for _, depth, _ in rows)
    width = MARGIN * 2 + max_depth * COL_W + NODE_W
    height = MARGIN * 2 + len(rows) * ROW_H
    return rows, edges, width, height


def _node_svg(span: dict[str, Any], depth: int, pos: int) -> str:
    x = MARGIN + depth * COL_W
    y = MARGIN + pos * ROW_H
    span_type = span.get("type", "unknown")
    has_error = bool(span.get("error"))
    icon = ERROR_ICON if has_error else TYPE_ICONS.get(span_type, UNKNOWN_ICON)
    fill = ERROR_FILL if has_error else SPAN_FILLS.get(span_type, "#f1f5f9")
    stroke = ERROR_COLOR if has_error else SPAN_COLORS.get(span_type, "#64748b")
    name = html.escape(str(span.get("name") or span_type))
    duration = html.escape(format_duration(_span_duration_seconds(span)))
    annotation = html.escape(str(span.get("annotation") or ""))
    return (
        f"<g>\n"
        f"<title>{annotation}</title>\n"
        f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="6" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
        f'<text x="{x + 10}" y="{y + 21}" font-size="13" font-weight="600" '
        f'fill="#0f172a">{icon} {name}</text>\n'
        f'<text x="{x + 10}" y="{y + 38}" font-size="11" fill="#475569">'
        f"{duration}</text>\n"
        f"</g>"
    )


def _span_duration_seconds(span: dict[str, Any]) -> float | None:
    started, ended = span.get("started_at"), span.get("ended_at")
    if not started or not ended:
        return None
    try:
        start = datetime.fromisoformat(started)
        end = datetime.fromisoformat(ended)
        return (end - start).total_seconds()
    except ValueError:
        return None
