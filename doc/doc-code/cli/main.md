# cli/main.py — main.py

> **文件路径**: `backend/packages/harness/agentflow/cli/main.py`
> **目录位置**: cli → main.py
> **职责**: 终端对话 CLI

## 📋 结构图

```text
┌──────────────────────────────────────────────────────────────┐
│ main()  [uv run agentflow]                                   │
│   ├─ 解析 --thread <id> 参数                                 │
│   ├─ load_dotenv()          ← 读项目根 .env（密钥）          │
│   ├─ load_config()          ← 读 config.yaml → AppConfig    │
│   ├─ init_db(db_path)       ← 建表（sessions 等）            │
│   ├─ create_sqlite_checkpointer(db_path) ← 图状态检查点      │
│   ├─ get_available_tools()  ← 工具目录（M2，5 个）            │
│   ├─ 中间件 2 个            ← 标题/线程目录（M2）            │
│   ├─ create_chat_model(cfg) ← 模型工厂 → ChatOpenAI          │
│   ├─ make_lead_agent(...)   ← 构建主 Agent（带持久化）       │
│   ├─ SessionRepository(conn) ← 会话记录 repo                 │
│   └─ 对话循环:                                               │
│        你 > 输入 → agent.stream({messages}, thread_id)       │
│              → 逐块打印回复 → 存消息记录 → 首轮标题落库       │
│              → 循环直到 exit                                 │
└──────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `main()`

## 💡 设计思想

1. 入口层只做装配（配置/模型/检查点/repo/工具/中间件），业务在 agents/。
2. 启动信息显示模型/工具/会话/数据：调试 P-014/015/016 全靠它
   （限流/流式问题第一时间看到是哪个模型/供应商）。
3. 对话循环容错：模型调用失败给友好提示不崩（P-015 限流实测）。
4. 从任何目录启动都能找到配置（Path(__file__) 定位，P-014）。

## 🎯 实用场景

1. 终端对话入口：uv run agentflow
2. 完整装配演示：config→db→checkpointer→tools→middlewares→model→agent→循环
3. 流式输出：langgraph stream 逐块打印（P-016 嵌套结构兼容）
4. 自动标题落库：首轮后 get_state 读 title → sessions.update_title
5. 启动信息：模型/工具/会话/数据一目了然（用户明确要求）
6. 调试与演示：无 Web UI 前的最快验证路径

## ❓ Q&A

**Q: 为什么启动信息要显示模型？**

A: P-014/015/016 调试全靠它——限流/流式问题第一时间看到是哪个模型/供应商

**Q: --thread 怎么用？**

A: 启动时打印的会话 ID 加 --thread 可继续上次对话（持久化验证入口）

## ⚠️ 风险点

1. Path(__file__).parents[5] 定位项目根，改目录层级会失效
2. _iter_chunk_messages 兼容嵌套/顶层两种 chunk 形态，勿简化
3. 首轮标题逻辑依赖 TitleMiddleware 写 state["title"]，两者需同步

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：main.py 头部注释 + 顶层符号。_
