"""OpenAI Agents SDK 接入示例（V3-P1）。

依赖：pip install "agenteval-debugger[agents-sdk]"
需要可用的模型 API（OPENAI_API_KEY，或 .env 里配 DeepSeek 兼容端点）。

运行：
    python examples/agents_sdk_demo.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from agents import Agent, Runner

import agenteval

# 自动读取项目根目录 .env（DeepSeek key / base_url 等），不引入额外依赖。
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# 注册 SDK TracingProcessor：进程内所有 Runner.run() 自动采集入库。
# 注意：这会替换 SDK 默认上传 OpenAI 平台的导出器，trace 只写本地 agenteval.db。
agenteval.init(
    db_path=os.environ.get("AGENTEVAL_DB", "agenteval.db"),
    agents_sdk=True,
    verbose=True,
)


async def main() -> None:
    agent = Agent(
        name="学习助手",
        instructions="你是中文学习助手，回答简洁、准确、有教学性。",
        # DeepSeek 等兼容端点需显式指定模型名；OpenAI 环境可改为 gpt-4o-mini。
        model=os.environ.get("AGENTEVAL_SDK_MODEL", "deepseek-v4-flash"),
    )
    result = await Runner.run(agent, "用一句话解释什么是 Agent？")
    print("回答：", result.final_output)
    trace = agenteval.last_trace()
    print("trace id：", trace["trace_id"] if trace else None)


if __name__ == "__main__":
    asyncio.run(main())
