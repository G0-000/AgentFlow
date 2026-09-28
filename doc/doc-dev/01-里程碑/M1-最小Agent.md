<!-- ============================================================
  AgentFlow doc · 文档注释
  更新时间: 2026-09-28
  维护约定: 本文件内容随里程碑推进更新；接手 AI 先读标题与正文引言。
  关联项目: AgentFlow（仿写 EvoFlow，原版参照 /Users/main/EvoFlow 只读）
================================================================ -->
# M1 — 最小 Agent 闭环（总览）

**状态：🟡 代码完成（20 文件），待真实 key 跑通对话**　**对应原版学习：Step 2 地基 + Step 3 前半**

> 本文档是 M1 的总览与导航。思考过程见 [M1-思考与规划](./M1-思考与规划.md)，各主题细节指向下方分文档。

---

## 1. 目标（一句话）

写一个最小 Agent：**加载配置 → 连上模型（DeepSeek/GLM）→ SQLite 存会话 → 能对话、重启进程还能接着聊**。

## 1.5 结构图（M1 一条对话怎么走完）

```
你 > 输入 ──► cli/main.py（uv run agentflow）
              │  load_dotenv(.env)            密钥
              │  load_config(config.yaml)     模型配置
              │  init_db(data/agentflow.db)   建表
              │  create_sqlite_checkpointer   图状态检查点
              │  create_chat_model            ChatOpenAI(DeepSeek)
              ▼
        make_lead_agent ──► create_agent(     ← langchain 官方 Agent
              │                    model=ChatOpenAI
              │                    tools=[]        （M1 空，M2 挂工具目录）
              │                    checkpointer    （每步存 SQLite）
              │                    system_prompt    （prompt.py 注入当前时间）
              ▼
        agent.stream({messages}, {thread_id})
              │  模型读 system prompt（含今天日期）→ 回复
              │  每步状态写 SQLite（同 thread_id 可恢复）
              ▼
你 < 回复（含真实日期：来自 prompt 注入，非工具调用）
```

## 2. 完成流程（四步）

```
① 先读原版 → ② 规划结构 → ③ 实现（20 个文件）→ ④ 验证
```

| 步骤 | 做了什么 | 详情 |
|---|---|---|
| ① 先读原版 | `thread_state.py` / `lead_agent/agent.py`（1700 行·30+ 中间件）/ config·persistence | [M1-思考与规划](M1-思考与规划.md) |
| ② 规划结构 | 目录照搬原版、文件砍 95%（config 36→4，persistence 60→6） | [M1-思考与规划](M1-思考与规划.md) · [目录结构](../02-架构设计/目录结构.md) |
| ③ 实现 | 双包 workspace + 20 文件（config/models/persistence/agents/tools/cli） | [模块实现](../04-模块实现/) |
| ④ 验证 | 配置✓ 建表✓ repo✓ agent构建✓ 真实对话🟡 | [验证记录](../05-验收体系/M1-验证记录.md) |

## 3. 核心思想（M1 要带走的 3 条）

1. **状态先行**：图里一切信息都在 `ThreadState` 这一个 dict 里流转——先搞清数据长什么样，再写逻辑
2. **检查点 = 持久化**：`SqliteSaver` 每步自动存 SQLite，同一 thread_id 重进即恢复
3. **工具与 Agent 解耦**：工具是独立单元（有 schema、有说明），Agent 只声明"用哪些"——M2 工具目录的地基

## 4. 交付一览（导航表）

| 域 | 文件 | 实现细节 |
|---|---|---|
| config/ | app_config · model_config · models_yaml · paths | [config-models域](../04-模块实现/config-models域.md) |
| models/ | factory · patched_openai | 同上 |
| persistence/ | db · schema · bootstrap · timestamps · repositories · session_repositories | [persistence域](../04-模块实现/persistence域.md) |
| agents/ | thread_state · checkpointer×2 · lead_agent/agent.py + prompt.py | [agents域](../04-模块实现/agents域.md) |
| tools/ | builtins/（M1 空壳——原版无独立时间工具，时间走 prompt 注入） | [tools-cli域](../04-模块实现/tools-cli域.md) |
| cli/ | main.py（`uv run agentflow`） | 同上 |

## 5. 验收清单

M1 共 5 个验收点（配置加载 / 建表 / Agent 构建 / 真实对话 / 会话持久化），
**每项的验收命令、通过标准、当前状态见**：[05-验收体系/M1-验收清单.md](../05-验收体系/M1-验收清单.md)。

当前进度：3/5 ✅，2/5 🟡（差 `.env` 真实 key）→ 填 key 后跑 `uv run agentflow` 即可完成。

## 6. 分文档导航

| 主题 | 文档 |
|---|---|
| 思考过程 / 规划原则 / 最小形态 | [01-里程碑/M1-思考与规划.md](M1-思考与规划.md) |
| 目录结构（对照原版） | [02-架构设计/目录结构.md](../02-架构设计/目录结构.md) |
| 设计决策（4 条 ADR） | [03-决策记录/](../03-决策记录/) |
| 各域实现说明 | [04-模块实现/](../04-模块实现/) |
| 验证清单与结果 | [05-验收体系/M1-验证记录.md](../05-验收体系/M1-验证记录.md) |

## 7. 下一步（M2）

工具目录（tool_catalog）+ SSE 流式输出 + 2 个中间件（记忆/标题雏形）。
