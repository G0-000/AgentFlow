# ============================================================================
# AgentFlow · community/web/provider.py —— 搜索 Provider 抽象基类（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/community/web/provider.py
# 对标来源: evoflow/community/web/provider.py（124 行裁剪：去掉 SQLite 设置/
#   config.yaml 回退的多层 key 读取，只留 ABC + env 直读 + placeholder 过滤）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ WebSearchProvider (ABC)                                    │
# │   ├─ name: str                稳定 id（如 "ddgs"）         │
# │   ├─ display_name: str        展示名                       │
# │   ├─ is_available() -> bool   环境/依赖就绪？(不碰网络)    │
# │   ├─ supports_search() -> bool 支持搜索？默认 True         │
# │   └─ search(query, limit) -> dict                          │
# │       成功: {"success": True, "data": {"web":[...]}}       │
# │       失败: {"success": False, "error": str}               │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 统一结果契约：不管背后是哪个搜索引擎，search 都返回同形状
#    {"success":bool, "data"/"error"}——上层（Agent 工具）只认契约不认引擎。
# 2. is_available 不碰网络：只查 env/依赖，供 registry 自动发现时快速判断。
# 3. env 直读 + placeholder 过滤：key 形如 "your-xxx"/"xxx"/"changeme" 视为未配置
#    （防止用户留着模板占位符当真实 key 用）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. WebSearchProvider: 抽象基类（子类必须实现 name/is_available/search）
# 2. get_provider_env: 读环境变量（带 placeholder 过滤）
# ----------------------------------------------------------------------------

from __future__ import annotations

import abc
import os
from typing import Any

_PLACEHOLDER_MARKERS = ("your-", "xxx", "placeholder", "example", "changeme", "todo", "replace")


def _looks_like_placeholder(value: str) -> bool:
    """判断字符串是否像模板占位符（未配置的真实 key）。"""
    v = (value or "").strip().lower()
    if not v:
        return True
    return any(m in v for m in _PLACEHOLDER_MARKERS)


def get_provider_env(name: str) -> str:
    """读环境变量；占位符/空值 → 返回 ""（视为未配置）。"""
    val = (os.getenv(name) or "").strip()
    return "" if _looks_like_placeholder(val) else val


class WebSearchProvider(abc.ABC):
    """可插拔的网页搜索后端。

    子类必须实现:
        name: 稳定 id（registry 注册键）
        is_available: 廉价可用性检查（只查 env/依赖，禁止网络 I/O）
        search: 执行搜索，返回统一契约 dict
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """稳定 id，用于 registry 注册与 search_backend 配置。"""

    @property
    def display_name(self) -> str:
        return self.name

    @abc.abstractmethod
    def is_available(self) -> bool:
        """廉价检查（env/依赖是否存在）。禁止网络 I/O。"""

    def supports_search(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        """执行搜索。默认实现返回不支持（子类覆盖）。"""
        return {"success": False, "error": f"{self.name} does not support search"}
