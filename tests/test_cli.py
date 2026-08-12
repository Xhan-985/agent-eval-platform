"""CLI 入口（agenteval-web / python -m agenteval）的单元测试。"""

import subprocess
import sys

import pytest

from agenteval import __main__ as entry
from agenteval.cli import web


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
