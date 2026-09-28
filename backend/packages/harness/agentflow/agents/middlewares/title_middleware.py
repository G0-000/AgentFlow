# ============================================================================
# AgentFlow · agents/middlewares/title_middleware.py —— 自动标题中间件
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/middlewares/title_middleware.py
# 对标来源: evoflow/agents/middlewares/title_middleware.py
#   原版：第一条用户消息后用 LLM 生成标题，写 state["title"]，
#   异步后台任务 + callback 抑制；M2 简化成【规则截断首条消息】，
#   保证验收稳定不依赖模型/限流。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ TitleMiddlewareState(AgentState)                           │
# │   title: NotRequired[str | None]                            │
# │                                                             │
# │ TitleMiddleware(AgentMiddleware)                            │
# │   state_schema = TitleMiddlewareState                       │
# │   before_model(state, runtime) → dict | None                │
# │     ① 取 messages 列表                                      │
# │     ② 仅"首条消息 + 尚无标题"时生成标题                     │
# │        title = 首条 user 消息前 20 字（规则截断）            │
# │     ③ 返回 {"title": title} → merge 进图状态                │
# │   （CLI 首轮对话后 get_state 读 title → 落库 sessions.title）│
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
# 2. 原版思想：标题是"横向能力"，挂在 AgentMiddleware 上，不进主图逻辑；
#    标题生成只做一次（首条消息），避免重复 LLM 调用。
# 3. M2 简化：用规则截断而非 LLM（免费模型限流会挂，P-015）；
#    后续想换 LLM 生成只需替换 _generate_title 内部实现。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. TitleMiddlewareState: 中间件状态（在 AgentState 上挂 title 字段）
# 2. TitleMiddleware: 自动标题中间件（before_model 钩子）
# 🔒 内部私有函数
# 1. _generate_title: 规则截断首条用户消息（≤20 字 + 省略号）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. _TITLE_MAX_CHARS=20 是标题长度上限，调整影响 CLI 显示与落库标题
# 2. 幂等保证：已有 title 时 before_model 返回 None，不会重复生成
# 3. 只认 messages[0] 为 human 才生成；系统注入类消息（type!=human）不触发
# ============================================================================
from __future__ import annotations

from typing import Any, NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AnyMessage

# 标题最长字数（CLI 显示美观 + 原版也控制长度）
_TITLE_MAX_CHARS = 20


class TitleMiddlewareState(AgentState):
    """与 ThreadState 兼容：额外挂一个 title 字段。"""

    title: NotRequired[str | None]


class TitleMiddleware(AgentMiddleware[TitleMiddlewareState]):
    """第一条用户消息后自动生成会话标题（写 state，CLI 落库）。"""

    state_schema = TitleMiddlewareState

    def _generate_title(self, first_message: AnyMessage) -> str:
        """生成标题：规则截断首条用户消息（M2 简化；原版用 LLM）。

        为什么不用 LLM：免费模型高峰限流（P-015）会让标题生成挂掉、
        拖慢首轮对话；规则截断 100% 稳定且足够可用。
        """
        content = str(getattr(first_message, "content", "") or "").strip()
        content = content.replace("\n", " ")
        if not content:
            return "新对话"
        return content[:_TITLE_MAX_CHARS] + ("…" if len(content) > _TITLE_MAX_CHARS else "")

    def before_model(self, state: TitleMiddlewareState, runtime) -> dict[str, Any] | None:
        """仅首条消息时生成一次标题（幂等：已有 title 则不重复）。"""
        messages: list[AnyMessage] = list(state.get("messages", []) or [])
        if not messages:
            return None
        if state.get("title"):
            return None  # 已有标题，不重复生成
        # 首条消息 = 用户的第一句话（human）
        first = messages[0]
        if getattr(first, "type", "") != "human":
            return None
        return {"title": self._generate_title(first)}
