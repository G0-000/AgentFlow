# ============================================================================
# AgentFlow · scripts/debug_agent_trace.py —— 解剖一条消息的执行链路（教学用）
# 用途: 把"用户输入 → 模型 → 工具 → 回填 → 回答"每一层的数据打印出来，
#       回答"消息如何解析、模型如何知道调哪个工具"这类问题。
# 跑法:
#   cd /Users/main/AgentFlow/backend
#   .venv/bin/python scripts/debug_agent_trace.py "帮我记一个待办：学完M2"
# 说明: 走真实模型（智谱）+ 真实工具链路；不挂中间件（聚焦主链路）。
# ============================================================================
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler

project_root = Path(__file__).resolve().parents[2]  # scripts → backend → 项目根
load_dotenv(project_root / ".env")

from agentflow.agents.checkpointer.provider import create_sqlite_checkpointer
from agentflow.agents.lead_agent.agent import make_lead_agent
from agentflow.agents.lead_agent.prompt import build_lead_agent_system_prompt
from agentflow.cli.main import _iter_chunk_messages
from agentflow.config.app_config import load_config
from agentflow.config.paths import default_db_path
from agentflow.knowledge.service import KnowledgeService
from agentflow.models.factory import create_chat_model
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.knowledge_repositories import KnowledgeRepository
from agentflow.tools.builtins.knowledge_tool import configure_knowledge_service
from agentflow.tools.tools import get_available_tools


class Trace(BaseCallbackHandler):
    """把模型调用 / 工具调用两层中间数据打印出来。"""

    def on_llm_start(self, serialized, prompts, **kwargs):
        print("\n" + "=" * 72)
        print("🟢 第 N 次模型调用 —— 模型此刻收到的 messages（一字不差）:")
        print("=" * 72)
        for i, p in enumerate(prompts):
            print(f"──── 消息 {i} ────")
            print(p)

    def on_llm_end(self, response, **kwargs):
        print("-" * 72)
        print("🟢 模型返回的原始响应（结构随 langchain 版本略变，抓不到就从 stream 块看）:")
        try:
            for gen in response.generations:
                msg = getattr(gen, "message", None)
                if msg is None or isinstance(msg, list):
                    continue  # 结构差异：真实输出见下方 stream chunk
                print(f"   type    = {msg.type!r}")
                print(f"   content = {msg.content!r}")
                if getattr(msg, "tool_calls", None):
                    print("   tool_calls = 结构化工具指令 JSON:")
                    for tc in msg.tool_calls:
                        print(f"     ├─ name: {tc['name']!r}   ← 选哪个工具")
                        print(f"     └─ args: {tc['args']!r}   ← 参数填什么")
        except Exception as exc:  # noqa: BLE001 回调失败不影响主链路
            print(f"   （回调读取失败: {type(exc).__name__}——见下方 chunk 输出）")
        print("-" * 72)

    def on_tool_start(self, serialized, input_str, **kwargs):
        print("🟠 框架解析 tool_calls → 按 name 找到工具并执行:")
        print(f"   工具名: {serialized.get('name')!r}")
        print(f"   工具收到的参数（JSON 字符串）: {input_str}")

    def on_tool_end(self, output, **kwargs):
        print(f"🟠 工具执行完毕，返回值（框架会包成 ToolMessage 回填给模型）:")
        print(f"   {output!r}")
        print("   → 工具结果已回填 messages；若 return_direct=True 则直接打印，")
        print("     若 False 则模型会基于它再生成一次回答（看下方是否出现第二次模型调用）")


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "帮我记一个待办：学完M2"

    # ── 装配（与 cli/main.py 相同，但不挂中间件）──
    cfg = load_config(str(project_root / "config.yaml"))  # 显式定位项目根配置（P-014）
    db_path = default_db_path()
    conn = init_db(db_path)
    checkpointer = create_sqlite_checkpointer(db_path)
    model = create_chat_model(cfg.models.chat)
    tools = get_available_tools()
    # 与 cli/main.py 相同的 M3 装配：知识库服务挂到 knowledge 工具（真实检索）
    knowledge = KnowledgeService(KnowledgeRepository(db_path=db_path), cfg.models.embedding)
    configure_knowledge_service(knowledge)
    system_prompt = build_lead_agent_system_prompt()
    agent = make_lead_agent(
        model=model, checkpointer=checkpointer, tools=tools, system_prompt=system_prompt
    )

    # ── 先给模型"看得到什么"：工具目录的说明书 ──
    print("=" * 72)
    print("模型启动时看到的工具说明书（每个工具的 name + description）:")
    print("=" * 72)
    for t in tools:
        desc = (t.description or "").splitlines()[0][:60]
        print(f"  - {t.name!r}: {desc}…")
    print("  （模型就是靠 description 决定何时调哪个工具）")

    # ── 用户输入如何进入图 ──
    print("\n" + "=" * 72)
    print("用户输入进入图 —— 框架包成 state:")
    print(f"  {{'messages': [{{'role': 'user', 'content': {question!r}}}]}}")
    print("  （AgentState.messages 用 reducer 累积，每轮都追加，不清空）")

    # ── 流式跑图，逐块解剖 ──
    print("\n" + "=" * 72)
    print("开始 stream() —— 图每走一步 yield 一个 chunk")
    print("=" * 72)
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        config={
            "configurable": {"thread_id": "debug-trace-1"},
            "callbacks": [Trace()],
        },
    ):
        # 这一步就是 CLI 的 _iter_chunk_messages：从 chunk 里挖消息
        print(f"\n  chunk 原始结构 keys = {list(chunk.keys())}")
        for m in _iter_chunk_messages(chunk):
            content = m.content if isinstance(m.content, str) else str(m.content)
            print(f"  → 挖到消息 type={m.type!r} content={content[:80]!r}")
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    print(f"    （内含工具指令: {tc['name']} {tc['args']}）")

    # ── 最终图状态：整条链路累积的消息 ──
    print("\n" + "=" * 72)
    print("最终图状态 st.values['messages']（完整消息链，按顺序）:")
    print("=" * 72)
    st = agent.get_state({"configurable": {"thread_id": "debug-trace-1"}})
    for m in st.values.get("messages", []):
        extra = ""
        if getattr(m, "tool_calls", None):
            extra = f" | tool_calls={[(tc['name'], tc['args']) for tc in m.tool_calls]}"
        if getattr(m, "tool_call_id", None):
            extra = f" | tool_call_id={m.tool_call_id!r}（回应哪次工具调用）"
        print(f"  - {m.type:6s} | {str(m.content)[:70]!r}{extra}")


if __name__ == "__main__":
    main()
