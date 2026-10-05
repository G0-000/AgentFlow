# ============================================================================
# AgentFlow · community/web/registry.py —— 搜索 Provider 注册中心（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/community/web/registry.py
# 对标来源: evoflow/community/web/registry.py（199 行裁剪：去掉 SQLite 设置读取/
#   EvoPanel 偏好后端解析，只留注册表 + 自动发现 + 后端解析）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ register_provider(p)   → _providers[name] = p（线程安全） │
# │ ensure_providers_loaded() → 首次自动注册内置 provider      │
# │ list_providers()       → 按 name 排序的全部 provider       │
# │ get_provider(name)     → 单个查询（None 若不存在）         │
# │ resolve_search_backend() → 选当前搜索后端（自动发现顺序）  │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 懒加载注册：第一次访问时才注册内置 provider（import 不触发副作用），
#    测试可随时 register 自定义 provider 覆盖。
# 2. 线程安全：RLock 包住读写（未来 scheduler/子代理并发取 provider 时不炸）。
# 3. 后端解析 = "env 显式指定优先，否则按内置优先级挑第一个可用"——
#    ddgs 免费无 key 永远是保底后端（原版 Hermes 默认无 key 兜底同款）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. register_provider: 注册一个 provider（类型校验 + name 校验）
# 2. list_providers / get_provider: 查询
# 3. resolve_search_backend: 解析当前搜索后端名
# ----------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import threading

from agentflow.community.web.provider import WebSearchProvider

logger = logging.getLogger(__name__)

_providers: dict[str, WebSearchProvider] = {}
_lock = threading.RLock()
_loaded = False

# 自动发现顺序（env 未显式指定时按此挑第一个可用）
_AUTO_PREFERENCE: list[str] = ["ddgs", "searxng", "tavily", "bocha"]


def register_provider(provider: WebSearchProvider) -> None:
    """注册一个搜索 provider。name 非空且不重复（重复覆盖）。"""
    if not isinstance(provider, WebSearchProvider):
        raise TypeError(f"expected WebSearchProvider, got {type(provider).__name__}")
    name = provider.name
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Web provider .name must be a non-empty string")
    with _lock:
        _providers[name.strip()] = provider
    logger.debug("Registered web provider '%s'", name)


def ensure_providers_loaded() -> None:
    """首次访问时注册内置 provider（幂等，线程安全）。"""
    global _loaded
    with _lock:
        if _loaded:
            return
        _loaded = True
    try:
        from agentflow.community.web.providers.ddgs import DDGSWebSearchProvider

        register_provider(DDGSWebSearchProvider())
    except Exception as exc:  # noqa: BLE001 —— 内置 provider 注册失败不影响 registry 空转
        logger.warning("Failed to register built-in providers: %s", exc)


def list_providers() -> list[WebSearchProvider]:
    """全部已注册 provider（按 name 排序）。"""
    ensure_providers_loaded()
    with _lock:
        items = list(_providers.values())
    return sorted(items, key=lambda p: p.name)


def get_provider(name: str) -> WebSearchProvider | None:
    """按 name 查 provider；不存在返回 None。"""
    ensure_providers_loaded()
    if not isinstance(name, str):
        return None
    with _lock:
        return _providers.get(name.strip())


def resolve_search_backend() -> str | None:
    """解析当前搜索后端名。

    顺序:
        1. 环境变量 AGENTFLOW_SEARCH_BACKEND 显式指定（存在且已注册 → 用之）
        2. 否则按 _AUTO_PREFERENCE 挑第一个 is_available() 的

    返回:
        选中的后端名；一个都不可用 → None。
    """
    ensure_providers_loaded()
    explicit = (os.getenv("AGENTFLOW_SEARCH_BACKEND") or "").strip()
    if explicit:
        provider = get_provider(explicit)
        if provider is not None and provider.is_available():
            return provider.name
    with _lock:
        registered = list(_providers.items())
    for name in _AUTO_PREFERENCE:
        provider = _providers.get(name)
        if provider is not None and provider.is_available():
            return name
    available = [name for name, p in registered if p.is_available()]
    return available[0] if available else None
