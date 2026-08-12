"""pytest 公共 fixture：隔离测试数据库，避免污染仓库目录。"""

import pytest

import agenteval


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """把 agenteval.init() 的默认数据库重定向到临时目录。"""
    real_init = agenteval.init

    def init_with_tmp(*args, **kwargs):
        kwargs.setdefault("db_path", str(tmp_path / "test.db"))
        return real_init(*args, **kwargs)

    monkeypatch.setattr(agenteval, "init", init_with_tmp)
    yield
