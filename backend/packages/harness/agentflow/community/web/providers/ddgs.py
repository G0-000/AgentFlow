# ============================================================================
# AgentFlow · community/web/providers/ddgs.py —— DuckDuckGo 免费搜索（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/community/web/providers/ddgs.py
# 对标来源: evoflow/community/web/providers/ddgs.py（84 行，几乎原样学）
#   去掉原版 logger 装饰与超时线程池细节保留（45s 超时是防挂关键）。
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ DDGSWebSearchProvider(WebSearchProvider)                   │
# │   ├─ name="ddgs" / display_name="DuckDuckGo (ddgs)"        │
# │   ├─ is_available(): import ddgs 成功即 True（无 key 依赖）│
# │   └─ search(query, limit):                                 │
# │        ThreadPoolExecutor(1) 带 45s 超时                   │
# │          → DDGS 客户端 text(query, backend=auto|bing)      │
# │          → 结构化 {"title","url","description","position"} │
# │        成功 → {"success":True,"data":{"web":[...]}}        │
# │        失败/超时 → {"success":False,"error":...}           │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 免费无 key：ddgs 库直连 DuckDuckGo，不需要 API key——
#    天然符合"测试不依赖真实 key"的纪律，也是默认保底后端。
# 2. 双后端兜底：auto 被墙/被封时回退 bing（国内网络常见），两个都失败才报错。
# 3. 45s 硬超时：网络搜索最怕挂起，线程池 + result(timeout) 保证最坏 45s 返回。
# 4. limit 夹紧 1..20：防上层传 9999 打爆上游。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. DDGSWebSearchProvider: ddgs 搜索后端（registry 内置注册）
# ----------------------------------------------------------------------------

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any

from agentflow.community.web.provider import WebSearchProvider

logger = logging.getLogger(__name__)

_SEARCH_TIMEOUT_SECS = 45


def _run_ddgs_search(query: str, safe_limit: int) -> list[dict[str, Any]]:
    """实际执行 ddgs 搜索（在子线程跑，带 45s 超时）。

    双后端（auto → bing）循环重试：国内网络 DDG HTML 常被拦，bing 兜底。
    """
    from ddgs import DDGS

    last_err: Exception | None = None
    for backend in ("auto", "bing"):
        try:
            results: list[dict[str, Any]] = []
            with DDGS(timeout=15) as client:
                for i, hit in enumerate(
                    client.text(query, max_results=safe_limit, backend=backend)
                ):
                    if i >= safe_limit:
                        break
                    url = str(hit.get("href") or hit.get("url") or "")
                    results.append(
                        {
                            "title": str(hit.get("title", "")),
                            "url": url,
                            "description": str(hit.get("body", "")),
                            "position": i + 1,
                        }
                    )
            if results:
                return results
        except Exception as e:  # noqa: BLE001 —— ddgs 后端失败换下一个
            last_err = e
            logger.info("ddgs backend=%s failed: %s", backend, e)
            continue
    if last_err is not None:
        raise last_err
    return []


class DDGSWebSearchProvider(WebSearchProvider):
    """DuckDuckGo（ddgs 库）免费搜索后端，无 API key。"""

    @property
    def name(self) -> str:
        return "ddgs"

    @property
    def display_name(self) -> str:
        return "DuckDuckGo (ddgs)"

    def is_available(self) -> bool:
        try:
            import ddgs  # noqa: F401

            return True
        except ImportError:
            return False

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        """执行搜索。统一契约：成功 {"success","data":{"web":[...]}} / 失败 error。"""
        safe_limit = max(1, min(int(limit), 20))
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_run_ddgs_search, query, safe_limit)
                web = fut.result(timeout=_SEARCH_TIMEOUT_SECS)
            if not web:
                return {"success": False, "error": "ddgs returned no results"}
            return {"success": True, "data": {"web": web}}
        except concurrent.futures.TimeoutError:
            return {"success": False, "error": f"ddgs search timed out after {_SEARCH_TIMEOUT_SECS}s"}
        except Exception as exc:  # noqa: BLE001 —— 网络异常统一转 error 契约
            logger.warning("ddgs search failed: %s", exc)
            return {"success": False, "error": f"ddgs search failed: {exc}"}
