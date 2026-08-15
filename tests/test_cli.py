"""CLI 入口（agenteval-web / python -m agenteval）的单元测试。"""

import os
import subprocess
import sys

import pytest

from agenteval import __main__ as entry
from agenteval.cli import load_dotenv, web


def test_load_dotenv_fills_missing_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nOPENAI_API_KEY=sk-test\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_dotenv(str(env_file))

    assert os.environ["FOO"] == "bar"
    assert os.environ["OPENAI_API_KEY"] == "sk-test"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "existing")

    load_dotenv(str(env_file))

    assert os.environ["FOO"] == "existing"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    load_dotenv(str(tmp_path / "nope.env"))  # 不应抛异常


def test_cli_web_launches_streamlit_with_python_m(monkeypatch):
    calls = []

    class _FakeProc:
        def __init__(self, returncode=0):
            self.returncode = returncode
            self.stdout = ""

    def fake_run(cmd, **kwargs):
        if "streamlit" in cmd:
            calls.append(cmd)
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        web()
    assert exc.value.code == 0
    assert len(calls) == 1
    assert calls[0][:4] == [sys.executable, "-m", "streamlit", "run"]
    assert calls[0][4].endswith("app.py")


def test_cli_web_propagates_streamlit_exit_code(monkeypatch):
    class _FakeProc:
        def __init__(self, returncode=0):
            self.returncode = returncode
            self.stdout = ""

    def fake_run(cmd, **kwargs):
        if "streamlit" in cmd:
            return _FakeProc(returncode=3)
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        web()
    assert exc.value.code == 3


def test_main_without_args_exits_with_usage(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["agenteval"])
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 1


def test_main_unknown_command_exits_1(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["agenteval", "foo"])
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 1


def test_main_web_delegates_to_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["agenteval", "web"])

    def fake_web():
        calls.append(True)

    monkeypatch.setattr("agenteval.cli.web", fake_web)
    entry.main()
    assert calls == [True]
