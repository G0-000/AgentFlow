# tools/builtins/todo_tool.py — todo_tool.py

> **文件路径**: `backend/packages/harness/agentflow/tools/builtins/todo_tool.py`
> **目录位置**: tools → builtins → todo_tool.py
> **职责**: 会话内待办工具

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ TodoStatus(str, Enum): pending / in_progress / done /      │
│                        cancelled（状态枚举）               │
│ TodoItem(@dataclass): id / title / status / created_at     │
│                                                             │
│ _todos: dict[str, TodoItem] —— 会话级内存存储              │
│                                                             │
│ todo_tool(action, item, id, title, status) -> str          │
│   @tool("todo", return_direct=True)                        │
│   add    → 新增待办（title 必填）                           │
│   list   → 列出全部（无则"（暂无待办）"）                  │
│   update → 按 id 改状态                                    │
│   delete → 按 id 删除                                      │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `TodoStatus`
- `TodoItem`

**函数**

- `todo_tool()`

**常量**

- `_TODO_DESCRIPTION`

## 💡 设计思想

1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §3
2. 原版语义：待办是"对话级 checklist"，不跨会话、不进任务中心——
   用户随手记的待办跟会话走，轻量、无持久化负担。
3. return_direct=True：工具结果直接回给用户，不再让模型二次加工，
   避免模型对结构化结果过度解读（照原版 clarification 工具模板）。
4. docstring 即说明书：_TODO_DESCRIPTION 就是给模型看的"何时用、
   参数怎么填"，工具体保持最简。

## 🎯 实用场景

1. 会话内待办：对话中"帮我记个待办"，Agent 自动调 add（实测：已添加待办: 学完M2（todo-1））
2. 任务跟进：list/update/delete 支撑对话中管理待办清单
3. M2 验收演示：工具自动调用链路的默认测试工具

## ⚠️ 风险点

1. _todos 是模块级内存 dict：进程重启即清空（当前设计，调试够用）
2. 待办 ID 用 len(_todos)+1 生成：删除后 ID 可能复用（可接受，或用 uuid）
3. 修改 _TODO_DESCRIPTION 会直接影响模型何时调用本工具（措辞要准）

## ❓ Q&A

**Q: todo 数据存内存还是存本地？会丢吗？**

A: 存内存（模块级 dict），进程重启即清空——**这是原版设计**。
原版 docstring 明说："conversation-scoped checklist, stored in memory and do NOT persist across conversations, never appear in 任务中心"。
需要跨会话/可分配的任务走任务中心（M7+ POST /api/tasks），todo 只服务"会话内随手记"。

**Q: 和原版有什么差异？**

A: 原版 `_todo_store: dict[str, list[TodoItem]]` **按 thread_id 分桶**（会话间隔离）；
M2 简化为单一 dict（所有会话共用一个池）。M3 改存储时对齐。

**Q: 想要持久化怎么办？**

A: 照原版语义 → 交给任务中心；真要落库 → M3+ 加 SQLite `todos` 表，只改函数体签名不动。

**Q: 模型如何从对话"读懂是待办"并调用本工具？（tool_calls 解析机制，2026-09-30）**

A: 链路三步，职责分离清晰：

```text
① 模型"读懂" = 读工具说明书，不是理解业务
   system prompt 里注入了每个工具的 description：
   "todo: 会话内待办清单工具…当用户要求'帮我记个待办'时使用。动作: add=添加待办（title 必填）…"
   模型把"帮我记一个待办：学完M2" 匹配到 description → 决定调 todo

② 模型输出结构化指令（tool_calls JSON），不是自然语言
   AIMessage(tool_calls=[{'name': 'todo', 'args': {'action': 'add', 'title': '学完M2'}}])
   注意：此时模型并没有"处理数据"——它只声明"我要调 todo，参数填这些"

③ 框架解析 + 工具处理数据
   解析: langchain 读 tool_calls → 按 name='todo' 在注册表里找到本工具（@tool 注册）
   校验: 按函数签名 schema 校验参数（action/title 类型、枚举合法性）
   执行: 调用 todo_tool(action='add', title='学完M2') → 内部写 _todos 并返回字符串
   回填: 返回字符串包成 ToolMessage（带 tool_call_id）回填给模型

一句话分工：
   模型决定"调哪个、参数填什么"（判断力）
   框架决定"找哪个工具、怎么校验调用"（调度力）
   工具自己处理数据（todo 函数体：写 dict / 格式化）
   结果回填给模型（return_direct=True 则直接打印）
```

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：todo_tool.py 头部注释 + 顶层符号。_
_2026-09-30 追加：Q&A 归档区（模型读懂→tool_calls→解析执行三步链路，用户提问自动归纳）。_
