# LangGraph callback 事件调研记录

> 调研时间：2026-08-09（Week 1 任务 2）
> 实测环境：langgraph 1.2.10 / langchain-core 1.5.3 / Python 3.14
> 用途：采集器实现依据。如依赖升级，需按本记录复核。

## 1. 事件到 span 类型映射

| 事件 | 触发时机 | span type | 关键参数 |
|------|---------|-----------|---------|
| `on_chain_start`（parent=None） | graph 根执行开始 | `agent_run` | `kwargs["name"]`="LangGraph"，`serialized`=None |
| `on_chain_start`（parent 非 None） | 节点执行开始 | `node` | 节点名在 `kwargs["name"]` 和 `metadata["langgraph_node"]` |
| `on_chat_model_start` | 聊天模型调用开始 | `llm_call` | `serialized["name"]` 是模型类名；`kwargs["invocation_params"]`/`["options"]` |
| `on_llm_start` | 旧式 LLM 调用（兼容保留） | `llm_call` | 同上，`prompts` 为渲染后的字符串 |
| `on_llm_end` | 模型调用结束 | - | `response.generations[0][*].text`、`response.llm_output["token_usage"]` |
| `on_tool_start` | tool 调用开始 | `tool_call` | `serialized["name"]`、`kwargs["tool_call_id"]`、`input_str` |
| `on_tool_end` | tool 调用结束 | - | `output` |
| `on_chain_error` / `on_llm_error` / `on_tool_error` | 出错 | - | `error` 异常对象 |

## 2. 关键发现（与旧文档假设的差异）

1. **聊天模型不再触发 `on_llm_start`**：LangChain 1.x 中 `BaseChatModel` 走 `on_chat_model_start`，`on_llm_start` 只对旧式 LLM 触发。采集器必须实现 `on_chat_model_start`，`on_llm_start` 保留为兼容。
2. **`on_chain_start` 的 `serialized` 是 None**：LangGraph 1.x 节点事件不传 serialized。节点名从 `kwargs["name"]` 或 `metadata["langgraph_node"]` 取；根事件 `kwargs["name"]` 恒为 "LangGraph"。
3. **模型调用参数在 kwargs 里**：`kwargs["invocation_params"]`（含模型配置、temperature 等）与 `kwargs["options"]` 是 replay 必需数据，必须采集进 metadata。
4. **错误链路**：tool 抛错时事件顺序为 `on_tool_error -> on_chain_error(节点) -> on_chain_error(根)`，且失败的节点不再触发 `on_chain_end`，采集器必须用 error 事件关闭 span。`graph.invoke` 会把原始异常向上抛。
5. **run_id 是 UUID 对象**：必须 `str()` 后才能作 dict key；根事件的 `parent_run_id=None`。
6. **callback 内部异常不会中断 Agent**：LangChain callback manager 会捕获并打印 `Error in ... callback`；采集器内部仍用 try-except 兜底（双保险）。
7. **tags 约定**：节点事件 `tags=["graph:step:N"]`，tool/模型事件 `tags=["seq:step:N"]`，可辅助排序与展示。
8. **节点输出是增量 state**：`on_chain_end` 的 outputs 只含本次节点改动的 key；根事件才含完整 state。

## 3. 探针验证方法

用一个 `StateGraph`（reason -> search_node）+ `FakeListChatModel` + `@tool` 打印全部事件即可复现。真实模型（ChatOpenAI）除 invocation_params 内容不同外，事件结构与 fake 一致。

## 4. 真实模型补充验证（2026-08-09）

用 `ChatOpenAI(gpt-4o-mini)` + `create_react_agent` 实测（此轮因 API key 401 未跑通成功路径，但错误路径已验证）：

- prebuilt agent 的 span 结构：`agent_run -> agent -> call_model / RunnableSequence -> Prompt -> llm_call(ChatOpenAI)`，Prompt 等内部 Runnable 会以 `node` span 出现。
- LLM 调用失败时触发 `on_llm_error`，llm_call span 的 error 被正确记录；错误沿 `RunnableSequence -> call_model -> agent -> 根` 逐级上抛。
- `create_react_agent` 在 LangGraph 1.0 已弃用（提示迁移到 `langchain.agents`），MVP 继续用 `langgraph.prebuilt` 并记录此限制。
- 成功路径（invocation_params 完整结构、token_usage、tool calling 事件）待有效 key 环境补充验证。
