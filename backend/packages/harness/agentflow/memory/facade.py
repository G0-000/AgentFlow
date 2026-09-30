# ============================================================================
# AgentFlow · memory/facade.py —— 记忆总入口
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/memory/facade.py
# 对标来源: evoflow/memory/facade.py（原版门面：命名空间/召回快照/资产）
#   M3 简化成两个动作: remember（沉淀）+ recall（取回注入）。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────┐
# │ MemoryFacade                                   │
# │   __init__(repo: MemoryRepository)              │
# │   remember(thread_id, role, content) → int     │
# │     委托 consolidate.extract_facts + 落库       │
# │   recall(thread_id=None, limit=10) → str       │
# │     取记忆 → 格式化段落（供注入系统提示词）     │
# │   count() → int（CLI 启动信息）                 │
# └────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 门面模式：业务方（CLI/中间件）只认识 MemoryFacade，
#    不直接碰 consolidate 细节或 repo SQL。
# 2. recall 跨会话（thread_id=None 取全部）：这是"新会话记得旧事实"
#    的入口（M3 验收点 1）。
# 3. 注入格式固定：CLI 把 recall() 结果拼进系统提示词即可。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. MemoryFacade: 记忆总入口（remember/recall/count）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. recall 返回字符串直接拼提示词；条数多时注意 token 长度
# 2. 记忆为空时返回空串（提示词里就没有记忆段，模型不困惑）
# ============================================================================

from __future__ import annotations

from agentflow.memory.consolidate import consolidate_message, extract_facts
from agentflow.persistence.memory_repositories import MemoryRepository


class MemoryFacade:
    """记忆总入口：沉淀 + 召回（M3 最小闭环）。"""

    def __init__(self, repo: MemoryRepository) -> None:
        self.repo = repo

    def remember(self, thread_id: str, role: str, content: str) -> int:
        """沉淀一条消息里的用户事实，返回沉淀条数。"""
        return consolidate_message(thread_id, role, content, self.repo)

    def recall(self, thread_id: str | None = None, limit: int = 10) -> str:
        """取记忆并格式化成提示词段落（跨会话，按时间倒序）。

        返回: 记忆段落；无记忆时返回空串。
        """
        rows = self.repo.recall(thread_id, limit=limit)
        if not rows:
            return ""
        lines = [f"- {r['content']}" for r in rows]
        return "已知关于用户的事实:\n" + "\n".join(lines)

    def count(self) -> int:
        """记忆总条数（CLI 启动信息）。"""
        return self.repo.count()

    # 供测试/工具用：直接暴露规则提取
    @staticmethod
    def extract_facts(text: str) -> list[str]:
        """规则提取用户事实（透传给 consolidate）。"""
        return extract_facts(text)
