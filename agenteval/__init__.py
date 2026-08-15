"""AgentEval — 面向学习者的 AI Agent 执行调试器。

用法（推荐）：

    import agenteval
    agenteval.init()
    traced = agenteval.wrap(graph)
    result = traced.invoke({...})
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

# 预导入诊断子模块：防止后续 `from agenteval.diagnose...` 覆盖同名公开函数属性。
from . import diagnose as _diagnose_module  # noqa: F401
from .collector.callback import AgentEvalCallbackHandler
from .collector.serializer import build_trace, serialize_to_json
from .storage.db import init_db, insert_trace

__version__ = "0.3.0"
__all__ = ["init", "wrap", "trace", "last_trace", "diagnose", "__version__"]

logger = logging.getLogger("agenteval")

_handler: AgentEvalCallbackHandler | None = None
_db_path: str = "agenteval.db"
_verbose: bool = False
_experiment_id: str | None = None
_llm_factory: Callable[[str], Any] | None = None
_last_trace: dict[str, Any] | None = None


def init(
    db_path: str = "agenteval.db",
    verbose: bool = False,
    experiment_id: str | None = None,
    llm_factory: Callable[[str], Any] | None = None,
) -> None:
    """初始化 AgentEval，创建采集 handler（幂等，可重复调用）。

    自动创建 SQLite 数据库与 traces 表（db_path 目录需存在）。
    experiment_id 用于标记实验组（V2 方案对比预留），不传则为 NULL。
    llm_factory 是 replay 用工厂函数（如 lambda model_name: ChatOpenAI(model=model_name)），
    不配置时 replay 会给出明确提示，其余功能不受影响。
    verbose=True 时，每次采集完成后会把 trace JSON 打印到控制台。
    """
    global _handler, _db_path, _verbose, _experiment_id, _llm_factory, _last_trace
    _db_path = db_path
    _verbose = verbose
    _experiment_id = experiment_id
    _llm_factory = llm_factory
    _handler = AgentEvalCallbackHandler(verbose=verbose)
    _last_trace = None
    init_db(db_path)


def last_trace() -> dict[str, Any] | None:
    """返回最近一次执行采集到的 trace（未采集过返回 None）。"""
    return _last_trace


def diagnose(
    trace_id: str,
    question: str | None = None,
    trace_id2: str | None = None,
    llm: Any | None = None,
    llm_factory: Callable[[str], Any] | None = None,
    model_name: str = "diagnose",
    max_steps: int = 8,
) -> str:
    """对一条（或两条）trace 运行无状态诊断 Agent，返回 Markdown 报告。

    复用 init() 配置的 llm_factory；handler 已初始化时，诊断过程本身会作为
    trace 入库（agent_name = "AgentEval 诊断助手"，吃自己的狗粮）。
    失败时返回明确中文错误文本，不抛异常。
    """
    from .diagnose.graph import diagnose as _run_diagnose

    factory = llm_factory or _llm_factory
    if _handler is not None:

        def run(graph: Any, state: dict[str, Any]) -> dict[str, Any]:
            return wrap(graph, name="AgentEval 诊断助手").invoke(state)

        return _run_diagnose(
            _db_path,
            trace_id,
            question=question,
            trace_id2=trace_id2,
            llm=llm,
            llm_factory=factory,
            model_name=model_name,
            max_steps=max_steps,
            run=run,
        )
    return _run_diagnose(
        _db_path,
        trace_id,
        question=question,
        trace_id2=trace_id2,
        llm=llm,
        llm_factory=factory,
        model_name=model_name,
        max_steps=max_steps,
    )


def wrap(graph: Any, name: str | None = None) -> Any:
    """包装 LangGraph graph，返回注入 callback 的包装对象。

    必须先用 init() 初始化。包装对象只支持同步 invoke；
    ainvoke / stream / astream 会抛 NotImplementedError。
    用户自带 config 会与注入的 callbacks 合并（保留 thread_id 等）。
    name 用于给 Agent 命名（列表页 Agent 列显示）；不传时回退到图的
    graph.name（LangGraph 默认 "LangGraph"）。
    """
    if _handler is None:
        raise RuntimeError("agenteval.init() 必须先于 wrap() 调用")
    _handler.agent_name = name if name is not None else getattr(graph, "name", None)
    return _TracedGraph(graph, _handler)


def trace(func: Callable) -> Callable:
    """装饰器：仅适用于签名包含 **kwargs 的函数。

    装饰器会把 callbacks=[handler] 通过 kwargs 传给原函数，
    原函数需要自行把 kwargs 传给 graph.invoke 的 config。
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if _handler is None:
            raise RuntimeError("agenteval.init() 必须先于使用 @agenteval.trace")
        _handler.reset()
        injected = dict(kwargs)
        injected["callbacks"] = [_handler]
        try:
            result = func(*args, **injected)
        except BaseException:
            _finalize_trace(_handler)
            raise
        _finalize_trace(_handler)
        return result

    return wrapper


class _TracedGraph:
    """同步 invoke 的 graph 包装器（Week 1 只支持 invoke）。"""

    def __init__(self, graph: Any, handler: AgentEvalCallbackHandler) -> None:
        self._graph = graph
        self._handler = handler

    def invoke(self, input, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        self._handler.reset()
        merged = _merge_config(config, {"callbacks": [self._handler]})
        try:
            result = self._graph.invoke(input, config=merged, **kwargs)
        except BaseException:
            _finalize_trace(self._handler)
            raise
        _finalize_trace(self._handler)
        return result

    def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("agenteval Week 1 只支持同步 invoke，请改用 .invoke()")

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("agenteval Week 1 只支持同步 invoke，请改用 .invoke()")

    def astream(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("agenteval Week 1 只支持同步 invoke，请改用 .invoke()")


def _merge_config(
    user_config: dict[str, Any] | None, injected: dict[str, Any]
) -> dict[str, Any]:
    """把注入的 callbacks 合并进用户 config，保留用户配置。"""
    if not user_config:
        return injected
    merged = dict(user_config)
    callbacks = list(merged.get("callbacks") or [])
    callbacks.extend(injected["callbacks"])
    merged["callbacks"] = callbacks
    return merged


def _finalize_trace(handler: AgentEvalCallbackHandler) -> None:
    global _last_trace
    try:
        trace = build_trace(handler)
    except ValueError:
        # 未采集到任何事件：清空上次 trace，避免 last_trace() 误返回历史值。
        _last_trace = None
        logger.warning("未采集到 trace：Agent 未产生任何 callback 事件")
        return
    _last_trace = trace
    _persist_trace(trace)
    if _verbose:
        print(serialize_to_json(trace))


def _persist_trace(trace: dict[str, Any]) -> None:
    """把 trace 写入 SQLite；失败只告警，不影响 Agent 执行。"""
    try:
        insert_trace(_db_path, trace, experiment_id=_experiment_id)
    except Exception:
        logger.exception("trace 写入 SQLite 失败（已忽略，不影响 Agent 执行）")
