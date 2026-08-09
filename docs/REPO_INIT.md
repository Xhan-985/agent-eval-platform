# AgentEval 仓库初始化方案

> 本文档说明仓库初始化的决策依据。README.md / .gitignore / LICENSE 已生成为独立文件，可直接使用。

---

## 1. GitHub 仓库名称建议

| 候选 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **agenteval** | 简洁、与 `pip install agenteval` 一致、好记 | 通用性强可能重名 | ⭐⭐⭐⭐⭐ |
| agenteval-py | 明确语言 | pip 包名不一致 | ⭐⭐ |
| agent-eval | 可读性好 | 连字符在 Python 包名要转下划线 | ⭐⭐⭐ |
| agenteval-debugger | 描述清晰 | 太长 | ⭐⭐ |

**推荐：`agenteval`**

理由：
1. 与 PyPI 包名一致（`pip install agenteval`），降低认知成本
2. 简短好记，社区传播友好
3. GitHub 搜索权重高（单一词汇）
4. 如果被占用，退而求其次用 `agenteval-debugger`

**检查占用**：访问 `github.com/agenteval` 确认是否已被占用。若占用，加 `-dev` 或 `-oss` 后缀。

---

## 2. 项目简介（Description）

### GitHub About（一句话，≤350 字符）

```
AgentEval — 面向学习者的 AI Agent 执行调试器。3 行代码接入 LangGraph，自动生成教学注释，支持 LLM 节点安全回放。
```

### 详细简介（用于 README 开头或社区推广）

```
AgentEval 是一个为 Agent 学习者和初学者设计的执行调试器。

现有 Agent 可观测工具（LangSmith、Langfuse、Phoenix）都面向资深工程师和企业场景，初学者上手门槛高，且不解释"Agent 为什么这么调"。

AgentEval 的三个差异化：
1. 教学化注释 — 每个 span 自动解释"这一步在干什么、为什么"
2. 安全回放 — LLM 节点可修改输入重跑，tool 节点用录播响应避免副作用
3. 3 行代码接入 — 比现有方案更简单

适合：Agent 学习者、教学演示、初学者调试。
不适合：企业级生产监控（用 Langfuse）。
```

### Topics（GitHub 仓库标签）

```
ai-agent, agent-debugger, langgraph, observability, tracing,
developer-tools, python, open-source, llm, agent-ops
```

---

## 3. README.md 初始内容

已生成为独立的 `README.md` 文件，可直接使用。

包含章节：
- 标题 + 一句话简介
- 特性（3 个差异化）
- 快速开始（3 行代码）
- 示例
- 路线图
- 贡献指南
- License

---

## 4. .gitignore 配置

已生成为独立的 `.gitignore` 文件，可直接使用。

覆盖：
- Python 标准忽略（`__pycache__`、`*.pyc`、`venv/`、`*.egg-info`）
- IDE（`.vscode/`、`.idea/`）
- 项目特定（`agenteval.db`、`traces/`、`.env`）
- OS（`.DS_Store`、`Thumbs.db`）
- 测试与覆盖率（`.pytest_cache/`、`.coverage`）

---

## 5. LICENSE 建议

**推荐：MIT License**

理由：
1. 最宽松，允许商业使用、修改、分发、私有化
2. Agent 生态主流选择（LangChain、LangGraph、Langfuse 都是 MIT）
3. 降低企业采用门槛（无 copyleft 限制）
4. 个人开源项目首选

**不推荐**：
- Apache 2.0：包含专利条款，对个人项目过重
- GPL：copyleft 限制企业采用

已生成为独立的 `LICENSE` 文件（MIT），把 `[year]` 和 `[fullname]` 替换为你的信息。

---

## 6. 项目目录结构

```
agenteval/
├── agenteval/                    # 主包
│   ├── __init__.py               # 对外 API
│   ├── collector/                # 采集层
│   │   ├── __init__.py
│   │   ├── callback.py
│   │   ├── annotator.py
│   │   └── serializer.py
│   ├── storage/                  # 存储层（Week 2）
│   │   └── __init__.py
│   ├── replay/                   # replay 层（Week 4）
│   │   └── __init__.py
│   └── web/                      # 展示层（Week 2-4）
│       └── __init__.py
├── examples/                     # 示例
│   └── react_agent_trace.py
├── tests/                        # 测试
│   ├── __init__.py
│   ├── test_callback.py
│   ├── test_serializer.py
│   └── test_annotator.py
├── docs/                         # 文档
│   └── HANDOVER.md
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml
└── .python-version
```

---

## 7. 第一批需要提交的文件（初始 commit）

初始 commit 只包含项目骨架，不含业务代码：

```
git commit -m "chore: initial project skeleton"
```

**文件清单**：

| 文件 | 内容 | 说明 |
|------|------|------|
| `.gitignore` | 已生成 | 忽略规则 |
| `LICENSE` | 已生成（MIT） | 替换作者信息 |
| `README.md` | 已生成 | 初始内容 |
| `pyproject.toml` | 最小配置 | 包名、版本、依赖 |
| `.python-version` | `3.10` | Python 版本 |
| `agenteval/__init__.py` | 占位 | `__version__ = "0.1.0"` |
| `agenteval/collector/__init__.py` | 空文件 | 模块占位 |
| `agenteval/storage/__init__.py` | 空文件 | 模块占位 |
| `agenteval/replay/__init__.py` | 空文件 | 模块占位 |
| `agenteval/web/__init__.py` | 空文件 | 模块占位 |
| `tests/__init__.py` | 空文件 | 测试包占位 |
| `examples/` | 空目录（加 .gitkeep） | 示例占位 |
| `docs/HANDOVER.md` | 已生成 | 开发交接文档 |

**不要提交**：
- 业务代码（Week 1 实现时再提交）
- `agenteval.db`（运行时生成）
- `.env`（含 API key）
- `__pycache__/`
- `venv/`

---

## 8. Git 提交规范建议

### 采用 Conventional Commits

格式：`<type>(<scope>): <subject>`

### Type 清单

| Type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(collector): implement callback handler` |
| `fix` | bug 修复 | `fix(serializer): handle missing parent_run_id` |
| `docs` | 文档变更 | `docs: update README quickstart` |
| `refactor` | 重构（不改功能） | `refactor(callback): extract span state to dataclass` |
| `test` | 测试相关 | `test(annotator): add error span cases` |
| `chore` | 杂项（构建、配置） | `chore: update dependencies` |
| `perf` | 性能优化 | `perf(serializer): optimize tree building` |
| `ci` | CI 配置 | `ci: add GitHub Actions workflow` |

### Scope 清单（项目特定）

| Scope | 对应模块 |
|-------|---------|
| `collector` | 采集层 |
| `serializer` | 序列化器 |
| `annotator` | 注释生成器 |
| `storage` | 存储层 |
| `replay` | replay 层 |
| `web` | Web 界面 |
| `api` | 对外 API（__init__.py） |
| `examples` | 示例 |
| `docs` | 文档 |
| `deps` | 依赖 |

### Subject 规范

- 用祈使句（英文）或动宾短语（中文）
- 不超过 50 字符
- 不加句号
- 首字母小写

### 示例提交

```
feat(collector): implement BaseCallbackHandler for LangGraph
fix(serializer): handle circular reference in state object
docs: add quickstart to README
test(annotator): add test cases for llm_call span
chore: initial project skeleton
refactor(api): make init() idempotent
```

### 分支策略（个人项目简化版）

```
main          # 可发布版本
dev           # 开发分支
feat/*        # 功能分支（如 feat/callback-handler）
fix/*         # 修复分支
```

**简化建议**：个人项目前期可以直接在 `main` 上开发，等有贡献者再引入分支策略。

### 版本规范

遵循 Semantic Versioning：

```
v0.1.0  # MVP 完成（Week 5）
v0.2.0  # 加诊断 Agent
v0.3.0  # 多框架支持
v1.0.0  # 第一个稳定版
```

Week 1-5 开发期用 `0.x.y`，不发 tag。MVP 完成后打 `v0.1.0` tag。

---

## 仓库初始化操作步骤

```bash
# 1. 创建仓库（GitHub 网页操作或 gh CLI）
gh repo create agenteval --public --description "AgentEval — 面向学习者的 AI Agent 执行调试器"

# 2. 克隆到本地
git clone https://github.com/<your-username>/agenteval.git
cd agenteval

# 3. 复制生成的文件
# 把 README.md / .gitignore / LICENSE 复制到仓库根目录
# 创建目录结构和占位文件

# 4. 初始提交
git add .
git commit -m "chore: initial project skeleton"
git push origin main

# 5. 设置 Topics（网页操作或 gh CLI）
gh repo edit --add-topic ai-agent,agent-debugger,langgraph,observability
```

---

*完成初始化后，把 HANDOVER.md 交给 Codex/Claude Code 开始 Week 1 开发。*
