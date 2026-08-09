# AgentEval 项目开发文档

> 版本：v1.0 | 更新时间：2026-08-09 | 状态：规划阶段

---

## 1. 项目背景和目标

### 1.1 背景

2025-2026 年 AI Agent 进入生产部署爆发期，但 Gartner 报告显示 **88% 的 Agent 试点项目无法跨越生产环境鸿沟**，首要原因是缺乏可观测性与调试能力。LangChain 2026 报告显示 57% 组织已部署 Agent，32% 将"质量"列为首要部署障碍。

当前 Agent 开发者面临的核心痛点：
- Agent 出错时不知道是检索错、推理错、还是 tool 返回脏数据
- 单个请求在多 Agent 系统中产生 40-200 个 span，人工读日志不可行
- 91% 生产 Agent 静默退化，开发者无感知

### 1.2 现有方案不足

| 方案 | 定位 | 不足 |
|------|------|------|
| LangSmith | 企业级 Agent 可观测平台 | 闭源、收费、面向资深工程师 |
| Langfuse | 开源 Agent 可观测平台 | 面向企业，学习者上手门槛高，不解释"为什么" |
| Arize Phoenix | 开源 LLM 可观测 | OTel 原生但偏 metric，教学化弱 |
| print 调试 | 原始方式 | 无法处理多步骤、无法回放 |

**核心空白**：现有方案都面向"资深工程师在企业环境调试生产 Agent"，没有面向"学习者和初学者理解 Agent 执行过程"的工具。

### 1.3 项目目标

**AgentEval 是面向 Agent 学习者的执行调试器**，让初学者能看懂 Agent 每一步在干什么、为什么这么调、出错时能安全回放定位。

三个目标：
1. **3 行代码接入**：比 Langfuse 接入更简单，降低学习者门槛
2. **教学化注释**：每个 span 自动解释"这一步在干什么、为什么"，现有方案不做
3. **安全 replay**：LLM 节点可重跑，tool 节点用录播响应回放，避免副作用

### 1.4 成功标准

- 学习者 3 行代码接入后，5 次点击内能定位 Agent 错误根因
- MVP 5 周内完成，可发布 PyPI
- 至少 1 个 LangGraph 示例项目集成演示

### 1.5 非目标

- 不做企业级监控告警平台
- 不做 Agent 评估打分平台
- 不做生产级长期日志存储
- 不与 Langfuse/Phoenix 正面竞争

---

## 2. 用户使用场景

### 2.1 核心用户画像

**主要用户**：Agent 学习者和初学者
- 软件工程专业学生
- 刚入门 Agent 开发的工程师
- 教学/布道者（用于演示 Agent 工作原理）

**非目标用户**：
- 企业级 Agent 运维团队（用 Langfuse/LangSmith）
- 资深 Agent 工程师（用 Phoenix/OTel 工具链）

### 2.2 场景一：学习时看不懂 Agent 执行过程

**用户故事**：小明是大学生，刚学 LangGraph，跟着教程写了一个 ReAct Agent。运行后 Agent 输出了奇怪的结果，他不知道 Agent 中间到底做了什么——调了几次 LLM、调了哪些 tool、每一步输入输出是什么。

**当前痛点**：加 print 看不懂、Langfuse 界面太复杂、教程不解释中间过程。

**AgentEval 解决**：接入后自动生成带教学注释的 trace 树，每个 span 解释"这一步是 Agent 在决定调用搜索工具，因为用户问了事实性问题"。

### 2.3 场景二：Agent 出错时定位根因

**用户故事**：小红写了一个多 tool Agent，运行时报错。她不知道是检索器找错文档、LLM 推理错、还是 tool 返回脏数据。

**当前痛点**：错误堆栈只指向最后一步，看不到完整决策链。

**AgentEval 解决**：打开 Web 界面看 trace 树，定位到具体 span，查看 input/output，确认是哪一步出问题。如果是 LLM 推理错，点 replay 修改 prompt 重跑，验证修复假设。

### 2.4 场景三：教学者展示 Agent 工作原理

**用户故事**：张老师教 AI Agent 课程，想给学生演示 ReAct Agent 的"思考-行动-观察"循环。

**当前痛点**：没有现成工具能可视化展示 Agent 内部循环。

**AgentEval 解决**：教学注释 + 树状图，学生能直观看到 Agent 的每一步推理。

---

## 3. 核心功能范围

### 3.1 In Scope（MVP 必须做）

| 功能 | 说明 | 优先级 |
|------|------|--------|
| Trace 采集 | 通过 LangGraph callback hook 采集执行轨迹 | P0 |
| 教学注释生成 | 为每个 span 自动生成"在干什么、为什么"的解释 | P0 |
| SQLite 存储 | trace 元数据 + JSON 内容统一存储 | P0 |
| Web 界面 | trace 列表 + 树状图可视化 + 注释展示 | P0 |
| 安全 replay（LLM 节点） | 修改 LLM 节点 input 重跑，tool 用录播响应 | P1 |

### 3.2 Out of Scope（MVP 不做）

| 功能 | 原因 |
|------|------|
| 多框架支持（OpenAI SDK、CrewAI） | MVP 只做 LangGraph，验证后再扩展 |
| 诊断 Agent（AI 助教） | V2 功能，等工具被用起来再加 |
| Tool 节点真实 replay | 副作用问题复杂，MVP 用录播响应 |
| 分布式部署 | 单机够用，不增加复杂度 |
| 用户系统、权限 | 个人工具，不需要 |
| 告警、监控 | 不是定位要做的事 |
| 评估打分 | 不是定位要做的事 |

### 3.3 差异化对比

| 能力 | Langfuse | Phoenix | AgentEval |
|------|----------|---------|-----------|
| 开源 | ✅ | ✅ | ✅ |
| 教学化注释 | ❌ | ❌ | ✅ |
| 面向学习者 | ❌ | ❌ | ✅ |
| 安全 replay | 部分 | ❌ | ✅（LLM 节点） |
| 3 行代码接入 | 5+ 行 | 5+ 行 | ✅ |
| 单机零配置 | 需 Docker | 需配置 | pip install 即用 |

---

## 4. MVP 版本定义

### 4.1 MVP 范围

**一句话定义**：LangGraph Agent 执行轨迹的采集、教学化可视化、LLM 节点安全回放工具。

**必含**：
- LangGraph callback 采集器
- span 教学注释生成器
- SQLite 存储层
- Streamlit Web 界面（列表 + 树状图 + 注释）
- LLM 节点 replay

**不含**：
- 多框架支持
- 诊断 Agent
- tool 节点真实 replay
- 任何企业级功能

### 4.2 MVP 验收标准

1. `pip install agenteval` 后，3 行代码能在 LangGraph Agent 上采集 trace
2. Web 界面能展示 trace 列表，点开能看到树状图
3. 每个 span 有教学注释，解释"这一步在干什么"
4. 选中 LLM 节点，修改 input，点 replay，能看到新的输出
5. 选中 tool 节点，显示"录播响应"提示，不真实执行
6. README 有完整上手示例，新用户 10 分钟内跑通

### 4.3 MVP 时间盒

5 周，详细规划见第 10 节。

---

## 5. 系统整体架构

### 5.1 架构总览

```
┌─────────────────────────────────────────────┐
│  开发者的 Agent 代码（LangGraph）              │
│  + 3 行接入代码                                │
└──────────────────┬──────────────────────────┘
                   │ callback events
                   ▼
┌─────────────────────────────────────────────┐
│  采集层（agenteval SDK）                       │
│  · LangGraph callback handler                 │
│  · span 教学注释生成器                         │
│  · trace JSON 序列化                          │
└──────────────────┬──────────────────────────┘
                   │ 写入
                   ▼
┌─────────────────────────────────────────────┐
│  存储层（SQLite 单库）                         │
│  · traces 表：元数据 + trace JSON             │
└──────────────────┬──────────────────────────┘
                   │ 查询
                   ▼
┌─────────────────────────────────────────────┐
│  展示层（Streamlit 单体）                      │
│  · trace 列表页                               │
│  · trace 树状图 + 教学注释                     │
│  · replay 面板（LLM 节点）                     │
└─────────────────────────────────────────────┘
```

### 5.2 架构原则

1. **单体优先**：MVP 阶段三层跑在一个进程，不拆服务
2. **零配置**：pip install 即用，不需要 Docker、不需要装数据库
3. **单一框架**：只支持 LangGraph，不做抽象层
4. **诚实降级**：tool 节点不能 replay 就明确提示，不假装能

### 5.3 为什么不用更复杂的架构

| 复杂架构 | 为什么不用 |
|----------|-----------|
| 微服务 | 单机单进程够用，拆了增加运维负担 |
| 消息队列 | 采集是同步的，不需要异步解耦 |
| PostgreSQL | SQLite 零配置，单机够用 |
| Redis | 无高频读写，不需要缓存 |
| Docker Compose | pip install 即用，不需要容器化 |
| React 前端 | Streamlit 一周出原型，React 至少三周 |

---

## 6. Agent 架构设计

### 6.1 核心原则

**AgentEval 本身不是 Agent 系统，是一个工具。** MVP 阶段不包含任何 Agent。

### 6.2 为什么 MVP 不做 Agent

1. **场景不需要**：采集、存储、可视化、replay 都是确定性工程问题，用传统代码更可靠
2. **避免堆砌**：硬塞 Agent 会增加复杂度、降低可靠性，违背"不堆技术"原则
3. **先验证工具价值**：等工具被学习者用起来，发现"我看不懂这个 trace"时，再加 AI 助教才名正言顺

### 6.3 V2 诊断 Agent 设计（MVP 后）

当 MVP 验证有用后，V2 加入**无状态诊断 Agent**：

- **角色**：AI 助教，帮学习者理解 trace
- **输入**：一个 trace_id
- **输出**：自然语言诊断报告（哪一步可能出错、为什么、建议怎么改）
- **无状态**：单次分析，不需要 Memory（MVP 后也不加 Memory，避免过度设计）
- **实现**：用 LangGraph 实现，吃自己的狗粮

### 6.4 诊断 Agent 的 Tool 设计（V2）

| Tool | 作用 | 为什么需要 |
|------|------|-----------|
| get_trace(trace_id) | 读取完整 trace | Agent 需要看全局 |
| get_span(trace_id, span_id) | 读取某 span 详情 | 定位具体步骤 |
| compare_traces(id1, id2) | 对比两个 trace | 找成功/失败差异 |

**只有 3 个 tool**，不贪多。诊断就是"看全局、看细节、做对比"三个动作。

### 6.5 为什么不做多 Agent 协作

- 诊断是单线程任务，不需要多 Agent 分工
- 多 Agent 通信引入复杂度，无收益
- A2A 协议是给跨服务 Agent 用的，这里用是过度设计

---

## 7. 各模块职责

### 7.1 模块划分

```
agenteval/
├── collector/          # 采集层
│   ├── callback.py     # LangGraph callback handler
│   ├── annotator.py    # 教学注释生成器
│   └── serializer.py   # trace JSON 序列化
├── storage/            # 存储层
│   ├── db.py           # SQLite 操作
│   └── schema.py       # 表结构定义
├── replay/             # replay 层
│   ├── runner.py       # 安全 replay 引擎
│   └── policy.py       # replay 策略（LLM/tool 区分）
├── web/                # 展示层
│   ├── app.py          # Streamlit 主入口
│   ├── list_view.py    # trace 列表页
│   ├── trace_view.py   # trace 树状图页
│   └── replay_view.py  # replay 面板
└── __init__.py         # 对外暴露 init/trace API
```

### 7.2 各模块职责

#### 采集层（collector）

| 模块 | 职责 | 为什么需要 |
|------|------|-----------|
| callback.py | 实现 LangGraph BaseCallbackHandler，接收 LLM/tool/state 事件 | 采集入口，没它没数据 |
| annotator.py | 根据 span 类型生成教学注释 | 核心差异化，让初学者看懂 |
| serializer.py | 把事件流组装成 trace JSON 树 | 存储和可视化都需要标准格式 |

**annotator 的关键设计**：
- LLM span 注释："Agent 正在调用 [模型名] 决定下一步，输入是 [上下文摘要]，输出选择了 [tool_choice]"
- tool span 注释："Agent 调用了 [tool名]，输入 [参数]，返回 [结果摘要]"
- handoff span 注释："控制权从 [Agent A] 交给 [Agent B]"
- error span 注释："⚠️ 这一步出错了：[错误信息]，可能原因是 [常见原因]"

#### 存储层（storage）

| 模块 | 职责 | 为什么需要 |
|------|------|-----------|
| db.py | SQLite 读写操作 | 持久化 |
| schema.py | 表结构 | traces 表：id, timestamp, status, framework, trace_json |

**为什么不用文件系统存 JSON**：一致性维护成本高，SQLite 的 TEXT 字段存 JSON 更简单。

#### replay 层（replay）

| 模块 | 职责 | 为什么需要 |
|------|------|-----------|
| runner.py | 执行 replay 逻辑 | 核心差异化 |
| policy.py | 判断 span 类型决定 replay 策略 | 安全性保障 |

**policy 的关键设计**：
- LLM 节点 → 真实重跑（无副作用）
- tool 节点 → 返回录播响应（避免副作用）
- handoff 节点 → 递归 replay 子节点

#### 展示层（web）

| 模块 | 职责 | 为什么需要 |
|------|------|-----------|
| app.py | Streamlit 主入口 | 用户界面入口 |
| list_view.py | trace 列表页 | 浏览历史 trace |
| trace_view.py | trace 树状图 + 注释 | 核心可视化体验 |
| replay_view.py | replay 面板 | 交互式调试 |

### 7.3 模块间依赖

```
web → storage → collector（单向依赖）
web → replay → storage
collector 不依赖 web/replay（采集时不需要它们）
```

**原则**：单向依赖，采集层可独立使用（不启动 Web 也能采集 trace）。

---

## 8. 数据流设计

### 8.1 采集流（写入）

```
开发者运行 Agent
    ↓
LangGraph 触发 callback 事件
    ↓
collector.callback 接收事件
    ↓
collector.annotator 生成教学注释
    ↓
collector.serializer 组装 trace JSON
    ↓
storage.db 写入 SQLite
    ↓
（可选）通知 Web 界面刷新
```

**为什么这样设计**：采集是同步的，事件发生即写入，不丢数据。不引入消息队列避免复杂度。

### 8.2 查询流（读取）

```
用户打开 Web 界面
    ↓
web.list_view 查询 trace 列表
    ↓
storage.db 返回元数据列表
    ↓
用户点开某条 trace
    ↓
web.trace_view 查询完整 trace JSON
    ↓
storage.db 返回 trace JSON
    ↓
web.trace_view 渲染树状图 + 注释
```

**为什么这样设计**：列表查元数据（快），详情查完整 JSON（按需），避免一次加载所有数据。

### 8.3 Replay 流（交互）

```
用户选中某 LLM span
    ↓
web.replay_view 展示原 input
    ↓
用户修改 input
    ↓
用户点"replay"按钮
    ↓
replay.policy 判断 span 类型
    ↓
┌─ LLM 节点 → replay.runner 调用 LLM 重跑 → 返回新 output
└─ tool 节点 → 返回录播响应 + 提示"这是历史结果"
    ↓
web.replay_view 展示对比（原 output vs 新 output）
```

**为什么 tool 节点不真实重跑**：
- tool 可能有副作用（发邮件、改数据库、调支付 API）
- 真实重跑会导致重复操作，可能造成损害
- 诚实告诉用户"这是录播"，比假装能 replay 更负责任

### 8.4 数据模型

**traces 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PRIMARY KEY | trace 唯一 ID（UUID） |
| created_at | TIMESTAMP | 创建时间 |
| status | TEXT | success / error / running |
| framework | TEXT | "langgraph"（MVP 固定） |
| agent_name | TEXT | Agent 名称 |
| trace_json | TEXT | 完整 trace JSON |

**trace JSON 结构**：

```
{
  "trace_id": "uuid",
  "root_span": {
    "span_id": "uuid",
    "type": "agent_run",
    "name": "ReAct Agent",
    "input": {...},
    "output": {...},
    "children": [
      {
        "span_id": "uuid",
        "type": "llm_call",
        "name": "gpt-4o",
        "input": {"messages": [...]},
        "output": {"tool_choice": "search", "content": "..."},
        "annotation": "Agent 正在决定下一步调用搜索工具",
        "children": [...]
      }
    ]
  }
}
```

**为什么用嵌套 JSON 而不是关系表**：trace 是树形结构，嵌套 JSON 更自然，SQLite 的 JSON 函数能查询，不需要 JOIN。

---

## 9. 技术选型及原因

### 9.1 技术栈总览

| 层 | 技术 | 版本 | 为什么选它 |
|----|------|------|-----------|
| 语言 | Python | 3.10+ | LangGraph 生态主流，大学生有基础 |
| Agent 框架 | LangGraph | 0.2+ | MVP 只支持它，用户基数大 |
| 存储 | SQLite | 内置 | 零配置，单机够用 |
| Web 框架 | Streamlit | 1.30+ | 一周出原型，Python 一套打通 |
| 可视化 | streamlit-mermaid / plotly | 最新 | 树状图现成组件 |
| 打包 | pip + PyPI | - | Python 标准方式 |

### 9.2 为什么不选其他技术

| 备选 | 为什么不选 |
|------|-----------|
| Node.js / TypeScript | 多学一门语言增加负担，LangGraph 生态在 Python |
| FastAPI + React | MVP 阶段过度工程，Streamlit 够用 |
| PostgreSQL | 需要安装配置，SQLite 零配置 |
| 向量数据库 | trace 是结构化树形数据，不需要向量检索 |
| Docker | pip install 即用，不需要容器化 |
| LangChain（而非 LangGraph） | LangGraph 是 LangChain 的 Agent 编排层，callback 更标准 |

### 9.3 依赖清单（极简）

MVP 阶段 `setup.py` 的核心依赖：
- `langgraph`（采集目标）
- `streamlit`（Web 界面）
- `sqlite3`（Python 内置，无需安装）

**只有 2 个第三方依赖**，降低用户接入成本。

---

## 10. 开发阶段规划

### 10.1 总览

| 阶段 | 时间 | 目标 | 产出 |
|------|------|------|------|
| Week 1 | 第 1 周 | 采集 SDK | 能采集带注释的 trace |
| Week 2 | 第 2 周 | 存储层 + 列表页 | 能在 Web 看 trace 列表 |
| Week 3 | 第 3 周 | 树状图可视化 | 核心体验跑通 |
| Week 4 | 第 4 周 | 安全 replay | 差异化能力 |
| Week 5 | 第 5 周 | 打磨 + 发布 | 可用产品 |

### 10.2 Week 1：采集 SDK

**目标**：实现 LangGraph callback handler，能采集 trace 并生成教学注释。

**任务**：
1. 研究 LangGraph callback 机制，确认事件类型
2. 实现 callback.py，接收 LLM/tool/state 事件
3. 实现 annotator.py，为每种 span 生成教学注释
4. 实现 serializer.py，组装 trace JSON
5. 对外暴露 `agenteval.init()` 和 `@agenteval.trace` API

**验收标准**：
- 在一个简单 LangGraph ReAct Agent 上接入，3 行代码
- 运行 Agent 后，能打印出带注释的 trace JSON
- trace JSON 结构正确（嵌套树形）

### 10.3 Week 2：存储层 + 列表页

**目标**：trace 入库，Web 界面能看列表。

**任务**：
1. 设计 traces 表结构
2. 实现 storage/db.py 的 CRUD 操作
3. 实现 Streamlit 主入口 app.py
4. 实现 list_view.py，展示 trace 列表
5. 支持按时间、状态、Agent 名筛选

**验收标准**：
- 采集的 trace 自动写入 SQLite
- 打开 Streamlit 能看到 trace 列表
- 列表显示时间、状态、Agent 名
- 筛选功能可用

### 10.4 Week 3：树状图可视化

**目标**：点开 trace 看到树状图 + 教学注释。

**任务**：
1. 选型树状图组件（streamlit-mermaid 或 plotly）
2. 实现 trace_view.py，渲染树状图
3. 每个节点展示 span 类型、名称、注释
4. 点击节点展开 input/output 详情
5. 错误 span 高亮显示

**验收标准**：
- 点开 trace 能看到完整树状图
- 每个 span 有教学注释
- 点击 span 能看 input/output
- 错误 span 视觉区分（红色标记）

### 10.5 Week 4：安全 replay

**目标**：LLM 节点可修改 input 重跑。

**任务**：
1. 实现 replay/policy.py，区分 span 类型
2. 实现 replay/runner.py，LLM 节点真实重跑
3. tool 节点返回录播响应 + 提示
4. 实现 replay_view.py，展示对比面板
5. 处理 replay 的错误情况（LLM 调用失败等）

**验收标准**：
- 选中 LLM span，修改 input，点 replay，能看到新 output
- 选中 tool span，显示"录播响应"提示，不真实执行
- 原output vs 新 output 对比展示
- replay 失败有明确错误提示

### 10.6 Week 5：打磨 + 发布

**目标**：可发布 PyPI，有完整文档。

**任务**：
1. 完善 README（3 行代码上手示例）
2. 编写端到端示例（用 LangGraph 官方示例集成）
3. 错误处理和边界情况
4. 性能优化（trace 大时的渲染）
5. 发布 PyPI
6. 准备社区推广材料（掘金/Reddit 帖子草稿）

**验收标准**：
- `pip install agenteval` 能安装
- README 的 quickstart 10 分钟跑通
- 至少 1 个完整示例项目
- PyPI 包可正常安装使用

---

## 11. 每个阶段的目标和验收标准

### 11.1 验收标准汇总

| 阶段 | 核心验收标准 | 衡量方式 |
|------|-------------|---------|
| Week 1 | 3 行代码接入，采集带注释 trace | 跑示例 Agent，打印 trace JSON |
| Week 2 | trace 入库，Web 列表可查 | 打开 Streamlit 看到列表 |
| Week 3 | 树状图 + 教学注释展示 | 点开 trace 看懂每一步 |
| Week 4 | LLM 节点 replay 可用 | 修改 input 重跑看新结果 |
| Week 5 | pip install 即用 | 新用户 10 分钟跑通 |

### 11.2 阶段门禁（Stage Gate）

每个阶段结束前必须满足：
- **功能完成度**：验收标准全部通过
- **可演示**：能给别人看（不是"在我机器上能跑"）
- **无阻塞问题**：已知问题有 workaround 或明确排期

**如果某周未达标**：
- Week 1 未达标 → 砍 Week 4 的 replay，保证核心可视化做好
- Week 3 未达标 → 砍 Week 4 的 replay，保证可视化质量
- Week 4 未达标 → replay 移到 V2，MVP 只做采集+可视化

### 11.3 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| LangGraph callback 机制变化 | 中 | 高 | Week 1 先验证，锁版本 |
| Streamlit 树状图性能差 | 中 | 中 | 限制 trace 大小，或换 plotly |
| replay 的 LLM 调用不稳定 | 中 | 中 | 加重试 + 超时 + 明确错误提示 |
| 没人用 | 高 | 高 | 主动推广 + 学习者定位降低门槛 |
| 时间不够 | 中 | 中 | 砍 replay 保采集+可视化 |

### 11.4 V2 路线图（MVP 后）

| 优先级 | 功能 | 为什么做 |
|--------|------|---------|
| V2-P0 | 诊断 Agent（AI 助教） | 体现 Agent 技术，从工具升级为智能助手 |
| V2-P1 | 多框架支持（OpenAI SDK） | 扩大用户基数 |
| V2-P2 | trace diff（对比两次执行） | 调试"以前能跑现在不能" |
| V2-P3 | 导出 Langfuse 格式 | 兼容性，让用户能迁移 |

---

## 附录：项目信息

- **项目名称**：AgentEval
- **定位**：Agent 学习者执行调试器
- **技术栈**：Python + LangGraph + Streamlit + SQLite
- **MVP 周期**：5 周
- **目标用户**：Agent 学习者、初学者、教学者
- **差异化**：教学化注释 + 安全 replay + 3 行代码接入
- **开源协议**：MIT

---

*本文档随项目进展持续更新。*
