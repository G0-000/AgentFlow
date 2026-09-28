# ============================================================================
# AgentFlow · cli/main.py —— 终端对话 CLI
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/cli/main.py
# 仿原: evoflow/cli/main.py（原版 CLI 是调试入口，正式入口在 gateway；
#       M1 先让 CLI 成为唯一入口，M7 再让位给 API）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图（M1 完整调用链，从上往下）:
# ┌──────────────────────────────────────────────────────────────┐
# │ main()  [uv run agentflow]                                   │
# │   ├─ 解析 --thread <id> 参数                                 │
# │   ├─ load_dotenv()          ← 读项目根 .env（密钥）          │
# │   ├─ load_config()          ← 读 config.yaml → AppConfig    │
# │   ├─ init_db(db_path)       ← 建表（sessions 等）            │
# │   ├─ create_sqlite_checkpointer(db_path) ← 图状态检查点      │
# │   ├─ create_chat_model(cfg) ← 模型工厂 → ChatOpenAI          │
# │   ├─ make_lead_agent(...)   ← 构建主 Agent（带持久化）       │
# │   ├─ SessionRepository(conn) ← 会话记录 repo                 │
# │   └─ 对话循环:                                               │
# │        你 > 输入 → agent.stream({messages}, thread_id)       │
# │              → 逐块打印回复 → 存消息记录                      │
# │              → 循环直到 exit                                 │
# └──────────────────────────────────────────────────────────────┘
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

# 配置域
from agentflow.config.app_config import load_config
from agentflow.config.paths import default_db_path

# 模型域（工厂）
from agentflow.models.factory import create_chat_model

# 持久化域（建表 / 会话 repo）
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.session_repositories import SessionRepository


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

    # ⑤ 模型 + ⑥ Agent：装配出可 stream 的编译图
    model = create_chat_model(cfg.models.chat)
    agent = make_lead_agent(model=model, checkpointer=checkpointer)

    # ⑦ 会话记录 repo（业务记录：会话 + 明文消息）
    sessions = SessionRepository(conn)

    # ⑧ 确定 thread_id（复用 or 新建），并保证会话行存在
    thread_id = args.thread or _generate_thread_id()
    sessions.create(thread_id)

    # ⑨ 启动信息：让控制台一眼看清"用的哪个模型 / 供应商 / 会话 / 数据"
    #    （需求：之前只显示会话 ID 太少；模型信息对调试很关键，P-014/015/016 都要靠它）
    reuse = "续用历史会话" if args.thread else "新会话"
    print(f"模型: {cfg.models.chat.model}（provider={cfg.models.chat.provider} @ {cfg.models.chat.base_url}）")
    print(f"会话: {thread_id}（{reuse}；--thread {thread_id} 可继续此会话）")
    print(f"数据: {db_path}")
    print("输入 exit 退出\n")

    # ⑩ 对话循环
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


if __name__ == "__main__":
    main()
