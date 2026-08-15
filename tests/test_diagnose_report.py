"""诊断报告结构（四段式 Markdown）与提示词模板的单元测试。"""

from agenteval.diagnose.prompts import SYSTEM_PROMPT, build_user_prompt
from agenteval.diagnose.report import (
    SECTIONS,
    has_complete_report,
    parse_report,
    render_report,
)


def test_system_prompt_mandates_four_sections():
    for section in SECTIONS:
        assert f"## {section}" in SYSTEM_PROMPT
    assert "span_id" in SYSTEM_PROMPT
    assert "中文" in SYSTEM_PROMPT


def test_build_user_prompt_contains_trace_and_question():
    prompt = build_user_prompt("t1", question="为什么报错？")
    assert "t1" in prompt
    assert "为什么报错？" in prompt


def test_build_user_prompt_with_compare_trace():
    prompt = build_user_prompt("t1", question=None, trace_id2="t2")
    assert "t1" in prompt
    assert "t2" in prompt


def test_parse_report_splits_four_sections():
    text = (
        "## 概述\n这段执行整体正常。\n\n"
        "## 可疑步骤\n- s-tool 出错。\n\n"
        "## 原因分析\n工具返回了脏数据。\n\n"
        "## 修改建议\n给工具调用加异常处理。"
    )
    sections = parse_report(text)
    assert sections == {
        "概述": "这段执行整体正常。",
        "可疑步骤": "- s-tool 出错。",
        "原因分析": "工具返回了脏数据。",
        "修改建议": "给工具调用加异常处理。",
    }


def test_parse_report_ignores_missing_sections():
    sections = parse_report("## 概述\n只有概述。")
    assert sections == {"概述": "只有概述。"}


def test_render_report_round_trips():
    sections = {
        "概述": "a",
        "可疑步骤": "b",
        "原因分析": "c",
        "修改建议": "d",
    }
    rendered = render_report(sections)
    assert has_complete_report(rendered)
    assert parse_report(rendered) == sections


def test_has_complete_report():
    complete = "\n".join(f"## {s}\n内容" for s in SECTIONS)
    assert has_complete_report(complete)
    assert not has_complete_report("## 概述\n只有概述。")
