# ============================================================================
# AgentFlow · cli/main.py —— 终端对话 CLI
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/cli/main.py
# 对标来源: evoflow/cli/main.py
#   原版 CLI 是调试入口，正式入口在 gateway；M1 先让 CLI 成为唯一入口，
#   M7 再让位给 API。
# 里程碑: M1（M2 接入工具/中间件/标题落库/启动信息）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ main()  [uv run agentflow]                                   │
# │   ├─ 解析 --thread <id> 参数                                 │
# │   ├─ load_dotenv()          ← 读项目根 .env（密钥）          │
# │   ├─ load_config()          ← 读 config.yaml → AppConfig    │
# │   ├─ init_db(db_path)       ← 建表（sessions 等）            │
# │   ├─ create_sqlite_checkpointer(db_path) ← 图状态检查点      │
# │   ├─ get_available_tools()  ← 工具目录（M2，5 个）            │
# │   ├─ 中间件 2 个            ← 标题/线程目录（M2）            │
# │   ├─ create_chat_model(cfg) ← 模型工厂 → ChatOpenAI          │
# │   ├─ make_lead_agent(...)   ← 构建主 Agent（带持久化）       │
# │   ├─ SessionRepository(conn) ← 会话记录 repo                 │
# │   └─ 对话循环:                                               │
# │        你 > 输入 → agent.stream({messages}, thread_id)       │
# │              → 逐块打印回复 → 存消息记录 → 首轮标题落库       │
# │              → 循环直到 exit                                 │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 入口层只做装配（配置/模型/检查点/repo/工具/中间件），业务在 agents/。
# 2. 启动信息显示模型/工具/会话/数据：调试 P-014/015/016 全靠它
#    （限流/流式问题第一时间看到是哪个模型/供应商）。
# 3. 对话循环容错：模型调用失败给友好提示不崩（P-015 限流实测）。
# 4. 从任何目录启动都能找到配置（Path(__file__) 定位，P-014）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. main: CLI 入口（pyproject [project.scripts] agentflow 指向它）
# 🔒 内部私有函数
# 1. _parse_args: --thread 参数解析
# 2. _generate_thread_id: 新会话 ID（时间戳+随机数）
# 3. _iter_chunk_messages: 从 langgraph stream chunk 递归取消息（P-016）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. Path(__file__).parents[5] 定位项目根，改目录层级会失效
# 2. _iter_chunk_messages 兼容嵌套/顶层两种 chunk 形态，勿简化
# 3. 首轮标题逻辑依赖 TitleMiddleware 写 state["title"]，两者需同步
# ============================================================================

from __future__ import annotations

import argparse
import os
from pathlib import Path

# dotenv: 读取项目根 .env 到环境变量（密钥不写进 yaml/代码）
from dotenv import load_dotenv

from agentflow.agents.checkpointer.provider import create_sqlite_checkpointer

# agents 域（主 Agent + 检查点）
from agentflow.agents.lead_agent.agent import make_lead_agent

# 中间件（M2）：自动标题 + 线程数据目录
from agentflow.agents.middlewares.thread_data_middleware import ThreadDataMiddleware
from agentflow.agents.middlewares.title_middleware import TitleMiddleware

# 配置域
from agentflow.config.app_config import load_config
from agentflow.config.paths import default_db_path

# 模型域（工厂）
from agentflow.models.factory import create_chat_model

# 持久化域（建表 / 会话 repo）
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.session_repositories import SessionRepository

# 工具域（M2）：工具收集 + 结果存取
from agentflow.tools.tools import get_available_tools


def _parse_args() -> argparse.Namespace:
    """命令行参数: --thread 复用会话（验证持久化的入口）。"""
    p = argparse.ArgumentParser(description="AgentFlow 终端对话")
    p.add_argument(
        "--thread",
        default=None,  # 缺省 = 新会话（自动生成 thread_id）
        help="复用指定会话 ID（thread_id），继续上次对话",
    )
    return p.parse_args()


def _generate_thread_id() -> str:
    """新会话 ID：时间戳 + 随机数（无需全局唯一检查，冲突概率可忽略）。"""
    return os.urandom(8).hex()


def _iter_chunk_messages(chunk: dict) -> list:
    """从 langgraph stream chunk 里取新增消息（递归）。

    langgraph 1.0.x create_agent 的 stream 输出是**节点嵌套结构**：
        {'model': {'messages': [AIMessage(...)]}}
    而不是顶层 {'messages': [...]}（CLI 曾直接取顶层导致空打印，见 P-016）。
    递归兼容两种形态，取到第一个 messages 列表即返回。
    """
    top = chunk.get("messages")
    if top:
        return top
    for v in chunk.values():
        if isinstance(v, dict):
            found = _iter_chunk_messages(v)
            if found:
                return found
    return []


def main() -> None:
    """CLI 入口：装配所有组件，进入对话循环。"""
    args = _parse_args()

    # ① 密钥：加载项目根 .env（AGENTFLOW_ROOT 向上找）
    #    config.yaml 里 ${DEEPSEEK_API_KEY} 由 models_yaml 在此之后展开
    project_root = Path(__file__).resolve().parents[5]
    load_dotenv(project_root / ".env")

    # ② 配置：config.yaml → AppConfig（路径/日志/模型）
    #    对齐原版：固定用项目根 config.yaml（Path(__file__).parents[N] 向上找），
    #    不依赖"从哪个目录启动"——否则在 backend/ 下跑会找不到根目录的 config.yaml
    cfg = load_config(str(project_root / "config.yaml"))
    if cfg.models is None or not cfg.models.chat.api_key:
        print("缺少模型配置：请检查 config.yaml 的 models 段，并在 .env 填写 API key")
        return

    # ③ 数据库：建表 + 连接（sessions/session_messages + checkpoint 表）
    db_path = default_db_path()
    conn = init_db(db_path)

    # ④ 检查点：图状态 → SQLite（同一 thread_id 恢复对话）
    checkpointer = create_sqlite_checkpointer(db_path)

    # ⑤ 工具（M2）：工具目录全量工具（5 个）
    tools = get_available_tools()

    # ⑥ 中间件（M2）：标题 + 线程数据目录（挂到 Agent 上，横向能力）
    middlewares = [TitleMiddleware(), ThreadDataMiddleware()]

    # ⑦ 模型 + ⑧ Agent：装配出可 stream 的编译图（模型↔工具循环）
    model = create_chat_model(cfg.models.chat)
    agent = make_lead_agent(
        model=model,
        checkpointer=checkpointer,
        tools=tools,
        middlewares=middlewares,
    )

    # ⑨ 会话记录 repo（业务记录：会话 + 明文消息）
    sessions = SessionRepository(conn)

    # ⑧ 确定 thread_id（复用 or 新建），并保证会话行存在
    thread_id = args.thread or _generate_thread_id()
    sessions.create(thread_id)

    # ⑩ 启动信息：让控制台一眼看清"用的哪个模型 / 供应商 / 会话 / 数据 / 工具"
    #    （需求：之前只显示会话 ID 太少；模型信息对调试很关键，P-014/015/016 都要靠它）
    reuse = "续用历史会话" if args.thread else "新会话"
    print(f"模型: {cfg.models.chat.model}（provider={cfg.models.chat.provider} @ {cfg.models.chat.base_url}）")
    print(f"工具: {len(tools)} 个（{', '.join(t.name for t in tools)}）")
    print(f"会话: {thread_id}（{reuse}；--thread {thread_id} 可继续此会话）")
    print(f"数据: {db_path}")
    print("输入 exit 退出\n")

    # ⑪ 对话循环
    first_turn = True
    while True:
        try:
            user_input = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("再见")
            break

        # 存用户消息（业务记录）
        sessions.add_message(thread_id, "user", user_input)

        # 跑图：LangGraph 内部循环（模型→工具→模型），逐块流式回传
        print("Agent > ", end="", flush=True)
        full_response = ""
        try:
            for chunk in agent.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config={"configurable": {"thread_id": thread_id}},  # 持久化维度
            ):
                # chunk 是节点输出字典；取 messages 里新增的 assistant 文本
                # （结构可能是 {'model': {...}} 嵌套，用 _iter_chunk_messages 兼容）
                for msg in _iter_chunk_messages(chunk):
                    text = getattr(msg, "content", "")
                    if text and isinstance(msg.content, str):
                        print(text, end="", flush=True)  # 流式（逐块打印）
                        full_response += text
        except Exception as exc:  # noqa: BLE001 —— 故意捕获所有模型调用异常（限流/欠费/网络抖动）给友好提示，不让调试 CLI 崩掉
            # 容错：模型服务端限流/欠费/网络抖动时给友好提示，不崩掉整个 CLI
            # （实测：智谱免费模型高峰期返回 code 1305 访问量过大，见问题日志 P-015）
            print(f"\n[模型调用失败] {type(exc).__name__}: {str(exc)[:200]}")
            full_response = f"(调用失败: {str(exc)[:120]})"
        print()  # 换行结束本轮

        # 存回复 + 刷新会话时间
        sessions.add_message(thread_id, "assistant", full_response)
        sessions.touch(thread_id)

        # 自动标题（M2）：首轮对话后读图状态里的 title（TitleMiddleware 生成），
        # 落库 sessions.title + 控制台提示。标题只生成一次（中间件幂等）。
        if first_turn:
            first_turn = False
            try:
                st = agent.get_state({"configurable": {"thread_id": thread_id}})
                title = (st.values or {}).get("title") if st else None
                if title:
                    sessions.update_title(thread_id, title)
                    print(f"\n[标题] {title}")
            except Exception:  # noqa: BLE001, S110 —— 标题失败不影响对话（无日志，调试期静默）
                pass


if __name__ == "__main__":
    main()
