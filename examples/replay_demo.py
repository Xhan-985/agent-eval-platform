"""AgentEval 安全 replay 演示。

用法：
    python examples/replay_demo.py            # fake 模式（无需 API key）
    python examples/replay_demo.py --real     # 真实 DeepSeek（需要 OPENAI_API_KEY）

流程：运行 Agent 采集 trace -> 取出 llm_call span -> 修改 input 重跑 ->
对比原/新 output；再演示 tool span 的录播响应（不真实执行）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from react_agent_trace import (  # noqa: E402
    _ensure_utf8_stdout,
    _load_dotenv_if_present,
    build_fake_graph,
    build_real_graph,
)

import agenteval  # noqa: E402
from agenteval.replay.runner import replay_span  # noqa: E402
from agenteval.web.trace_view import flatten_spans  # noqa: E402


def _make_fake_factory():
    """fake 工厂：返回 FakeListChatModel，无需 API key。"""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    return lambda model_name: FakeListChatModel(
        responses=["（fake replay）这是修改输入后的新回答。"]
    )


def _make_real_factory():
    """real 工厂：DeepSeek（OpenAI 兼容端点）。"""
    from langchain_openai import ChatOpenAI

    return lambda model_name: ChatOpenAI(
        model=model_name,
        base_url="https://api.deepseek.com",
        api_key=os.environ.get("OPENAI_API_KEY"),
        temperature=0,
    )


def _print_output(label: str, value) -> None:
    text = value.content if hasattr(value, "content") else str(value)
    print(f"{label}: {text[:160]}")


def main() -> None:
    _ensure_utf8_stdout()
    _load_dotenv_if_present()
    mode = "real" if "--real" in sys.argv else "fake"
    print(f"replay 演示（{mode} 模式）")

    factory = _make_real_factory() if mode == "real" else _make_fake_factory()
    agenteval.init(verbose=False, llm_factory=factory)

    if mode == "real":
        graph = build_real_graph()
        input_data = {"messages": [("user", "用一句话介绍 LangGraph")]}
    else:
        graph = build_fake_graph()
        input_data = {"query": "LangGraph 是什么？", "messages": []}

    agenteval.wrap(graph).invoke(input_data)
    trace = agenteval.last_trace()
    print("trace status:", trace["status"])

    spans = flatten_spans(trace)
    llm_span = next((s for s in spans if s["type"] == "llm_call"), None)
    tool_span = next((s for s in spans if s["type"] == "tool_call"), None)

    if llm_span is not None:
        print("\n--- LLM span replay（真实重跑） ---")
        new_input = dict(llm_span["input"])
        new_input["messages"] = new_input.get("messages", []) + [
            {"type": "human", "content": "（replay 演示）请补充说明。"}
        ]
        result = replay_span(llm_span, new_input, factory)
        _print_output("原 output", result["original_output"])
        _print_output("新 output", result["replayed_output"])
        print("error:", result["error"])
    else:
        print("未找到 llm_call span")

    if tool_span is not None:
        print("\n--- tool span 录播响应（不真实执行） ---")
        result = replay_span(tool_span, None, factory)
        print("is_recorded:", result["is_recorded"])
        print("output:", str(result["replayed_output"])[:120])
    else:
        print("未找到 tool_call span")


if __name__ == "__main__":
    main()
