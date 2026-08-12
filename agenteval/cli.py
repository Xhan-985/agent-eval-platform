"""AgentEval CLI 入口。"""


def web() -> None:
    """启动 Streamlit Web 界面。

    用法：安装后直接在终端运行 agenteval-web
    需要先安装 web 依赖：pip install "agenteval[web]"
    """
    import subprocess
    import sys

    from agenteval.web import app as app_module

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", app_module.__file__],
        check=False,
    )
