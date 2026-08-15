"""诊断层：无状态诊断 Agent（AI 助教）。

只读依赖 storage，不依赖 collector / replay / web。
"""

from .graph import DiagnoseState, build_diagnose_graph, diagnose
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .report import SECTIONS, has_complete_report, parse_report, render_report
from .tools import TOOL_DISPATCH, TOOL_SPECS, compare_traces, get_span, get_trace

__all__ = [
    "diagnose",
    "build_diagnose_graph",
    "DiagnoseState",
    "get_trace",
    "get_span",
    "compare_traces",
    "TOOL_SPECS",
    "TOOL_DISPATCH",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "SECTIONS",
    "parse_report",
    "render_report",
    "has_complete_report",
]
