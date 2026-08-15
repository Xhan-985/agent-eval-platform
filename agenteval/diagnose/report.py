"""诊断报告结构：四段式 Markdown 的解析 / 渲染 / 校验。"""

from __future__ import annotations

import re
from typing import Any

SECTIONS = ["概述", "可疑步骤", "原因分析", "修改建议"]

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_report(text: str) -> dict[str, str]:
    """把四段式 Markdown 按二级标题拆分；缺失章节不输出。"""
    matches = list(_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        if heading not in SECTIONS:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[heading] = text[start:end].strip()
    return sections


def render_report(sections: dict[str, str]) -> str:
    """把章节 dict 渲染成四段式 Markdown（仅输出非空章节）。"""
    blocks = [
        f"## {name}\n{sections[name].strip()}"
        for name in SECTIONS
        if name in sections and sections[name].strip()
    ]
    return "\n\n".join(blocks)


def has_complete_report(text: str) -> bool:
    """报告是否包含全部四个章节标题。"""
    return all(f"## {section}" in text for section in SECTIONS)


__all__: list[str] = ["SECTIONS", "parse_report", "render_report", "has_complete_report"]
