# ============================================================================
# AgentFlow · tests/test_community_search.py —— 第三方搜索集成（M6）
# 验收项：②第三方集成——搜索返回真实形状的结构化结果。
# registry 用注册/解析直测；ddgs search 用 monkeypatch 模拟上游，不碰真实网络。
# ============================================================================
from agentflow.community.web.provider import WebSearchProvider, get_provider_env
from agentflow.community.web.registry import (
    get_provider,
    list_providers,
    register_provider,
    resolve_search_backend,
)


class FakeProvider(WebSearchProvider):
    """测试用假 provider：固定返回成功契约。"""

    @property
    def name(self) -> str:
        return "fake"

    @property
    def display_name(self) -> str:
        return "Fake"

    def is_available(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> dict:
        return {
            "success": True,
            "data": {"web": [{"title": f"r-{query}", "url": "http://x", "description": "d", "position": 1}]},
        }


class UnavailableProvider(WebSearchProvider):
    @property
    def name(self) -> str:
        return "unavail"

    def is_available(self) -> bool:
        return False

    def search(self, query: str, limit: int = 5) -> dict:
        return {"success": False, "error": "nope"}


# ── registry ──────────────────────────────────────────────


def test_register_list_get_roundtrip():
    register_provider(FakeProvider())
    assert [p.name for p in list_providers()].count("fake") >= 1
    assert get_provider("fake").name == "fake"
    assert get_provider("not-exists") is None


def test_register_type_error():
    import pytest

    with pytest.raises(TypeError, match="expected WebSearchProvider"):
        register_provider("not-a-provider")  # type: ignore[arg-type]


def test_resolve_backend_env_explicit(monkeypatch):
    register_provider(FakeProvider())
    monkeypatch.setenv("AGENTFLOW_SEARCH_BACKEND", "fake")
    assert resolve_search_backend() == "fake"


def test_resolve_backend_auto_falls_to_first_available(monkeypatch):
    register_provider(UnavailableProvider())
    monkeypatch.delenv("AGENTFLOW_SEARCH_BACKEND", raising=False)
    backend = resolve_search_backend()
    # ddgs 已安装（依赖）→ 默认可用；unavail 不可用被跳过
    assert backend is not None
    assert backend != "unavail"


# ── provider env 读取 ─────────────────────────────────────


def test_get_provider_env_placeholder_filtered(monkeypatch):
    monkeypatch.setenv("FAKE_KEY", "your-api-key-here")
    assert get_provider_env("FAKE_KEY") == ""
    monkeypatch.setenv("FAKE_KEY", "real-key-123")
    assert get_provider_env("FAKE_KEY") == "real-key-123"


# ── 验收点 ②：ddgs 搜索统一契约 ───────────────────────────


def test_ddgs_search_success_shape(monkeypatch):
    from agentflow.community.web.providers import ddgs as ddgs_mod

    fake_hits = [
        {"href": "http://a.com", "title": "A", "body": "desc-a"},
        {"href": "http://b.com", "title": "B", "body": "desc-b"},
    ]

    def fake_run(query, safe_limit):
        return [
            {"title": h["title"], "url": h["href"], "description": h["body"], "position": i + 1}
            for i, h in enumerate(fake_hits[:safe_limit])
        ]

    monkeypatch.setattr(ddgs_mod, "_run_ddgs_search", fake_run)
    provider = ddgs_mod.DDGSWebSearchProvider()
    result = provider.search("你好")
    assert result["success"] is True
    web = result["data"]["web"]
    assert len(web) == 2
    assert web[0]["title"] == "A"
    assert web[0]["url"] == "http://a.com"
    assert web[0]["position"] == 1


def test_ddgs_search_limit_clamped(monkeypatch):
    from agentflow.community.web.providers import ddgs as ddgs_mod

    seen = {}

    def fake_run(query, safe_limit):
        seen["limit"] = safe_limit
        return []

    monkeypatch.setattr(ddgs_mod, "_run_ddgs_search", fake_run)
    provider = ddgs_mod.DDGSWebSearchProvider()
    provider.search("q", limit=999)
    assert seen["limit"] == 20  # 夹到 20


def test_ddgs_search_failure_contract(monkeypatch):
    from agentflow.community.web.providers import ddgs as ddgs_mod

    def fake_run(query, safe_limit):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(ddgs_mod, "_run_ddgs_search", fake_run)
    provider = ddgs_mod.DDGSWebSearchProvider()
    result = provider.search("q")
    assert result["success"] is False
    assert "upstream down" in result["error"]


def test_ddgs_is_available_when_installed():
    from agentflow.community.web.providers.ddgs import DDGSWebSearchProvider

    assert DDGSWebSearchProvider().is_available() is True
