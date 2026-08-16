"""AgentEval CLI 入口。"""

from __future__ import annotations

import os


def load_dotenv(path: str = ".env") -> None:
    """极简 .env 加载：仅为未设置的变量填充，不覆盖已有环境变量。"""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def web() -> None:
    """启动 Streamlit Web 界面。

    用法：安装后直接在终端运行 agenteval-web
    需要先安装 web 依赖：pip install "agenteval[web]"
    """
    import subprocess
    import sys

    load_dotenv()
    from agenteval.web import app as app_module

    proc = subprocess.run(
        [sys.executable, "-m", "streamlit", "run", app_module.__file__],
        check=False,
    )
    sys.exit(proc.returncode)


def demo() -> None:
    """一键生成演示 trace（fake 模式，无需 API key），并提示如何打开 Web。"""
    import sys

    load_dotenv()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    from agenteval.demo import generate_demo_traces

    summary = generate_demo_traces()
    print(f"已生成 {len(summary)} 条演示 trace：")
    for item in summary:
        status_text = "成功" if item["status"] == "success" else "失败"
        print(f"  [{status_text}] {item['label']}  trace_id: {item['trace_id'][:8]}…")
    print("\n打开可视化页面查看：")
    print("  python -m agenteval web   →  http://localhost:8501")
