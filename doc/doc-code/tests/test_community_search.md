# tests/test_community_search.py — test_community_search.py

> **文件路径**: `backend/packages/harness/tests/test_community_search.py`
> **目录位置**: tests → test_community_search.py
> **职责**: 第三方搜索集成测试（M6 验收点 2）——registry 注册/解析 + ddgs 统一结果契约

## 📑 目录

- [📋 结构图](#📋-结构图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🧩 代码解析（成块对照 test_community_search.py）](#🧩-代码解析成块对照-test_community_searchpy)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图

```text
tests/test_community_search.py（9 用例 → 验收点 2：第三方集成）
├── registry（4）
│   ├── test_register_list_get_roundtrip        注册/列表/查询往返
│   ├── test_register_type_error                非 Provider → TypeError
│   ├── test_resolve_backend_env_explicit       AGENTFLOW_SEARCH_BACKEND 显式指定
│   └── test_resolve_backend_auto_falls_to_first_available  自动挑可用后端
├── env 读取（1）
│   └── test_get_provider_env_placeholder_filtered  占位符 key 视为未配置
└── ddgs 契约（4）
    ├── test_ddgs_search_success_shape          成功 → {"success","data":{"web":[...]}}
    ├── test_ddgs_search_limit_clamped          limit 夹到 20
    ├── test_ddgs_search_failure_contract       异常 → {"success":False,"error"}
    └── test_ddgs_is_available_when_installed   依赖存在即可用

被测对象: agentflow/community/web/{provider,registry}.py + providers/ddgs.py
```

## 📤 关键导出

无独立导出（测试文件）。覆盖的被测契约：

- `register_provider / list_providers / get_provider`：注册表线程安全增删查
- `resolve_search_backend`：env 显式优先 → 自动发现兜底
- `get_provider_env`：占位符过滤
- `DDGSWebSearchProvider.search`：统一契约（成功 data.web / 失败 error）

## 💡 设计思想

1. **monkeypatch 替代真实网络**：`_run_ddgs_search` 是 ddgs 与上游的唯一接触点——测试替换它返回假命中，断言上层契约不变（验收点 2 证明"搜索返回结构化结果"的形状，不依赖真实网络可用性）。
2. **统一契约是核心**：不管上游怎么变，`{"success": True, "data": {"web": [title/url/description/position]}}` 形状必须稳定——上层 Agent 工具只认这个形状。
3. **limit 夹紧有测试**：传 999 断言收到 20——防上层误传大数打爆上游。
4. **registry 懒加载可注入**：测试注册 FakeProvider 覆盖，说明注册表对外部 provider 开放（未来接 tavily/bocha 同款注册）。

## 🧩 代码解析（成块对照 test_community_search.py）

### 块 1：ddgs 成功契约

```python
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
```

**整块解析**（参数逐条）：

| 步骤 | 动作 | 作用 |
|---|---|---|
| `fake_hits` | 构造两条假上游命中 | href/title/body 对应 ddgs 原始返回键 |
| `fake_run(query, safe_limit)` | 假 `_run_ddgs_search` | 返回统一形状的命中（含 position）——替代真实 ddgs 库 |
| `monkeypatch.setattr(ddgs_mod, "_run_ddgs_search", fake_run)` | 替换模块函数 | 拦截 ddgs 与上游的接触点，不碰网络 |
| `provider.search("你好")` | 调搜索 | 走 provider 层（超时/夹紧逻辑保留，只换数据源） |
| `assert result["success"] is True` | 成功契约 | 上层可信任 success 分支 |
| `assert web[0]["title"] == "A"` | 字段形状 | title/url/description/position 四个字段齐全且有序 |

**关键细节**：`provider.search` 内部的 `ThreadPoolExecutor + 45s 超时 + limit 夹紧` 都真实执行——只有数据源被替换，契约与防护逻辑照常验证。

## ⚠️ 风险点

1. **monkeypatch 只换数据源**：ddgs 库本身（auto/bing 双后端重试逻辑在 `_run_ddgs_search` 内）未被测——真实网络路径依赖测试外的验证。
2. **registry 是进程级全局**：多个测试文件同进程跑时，register_provider 注册的 FakeProvider 会残留——`get_provider("fake")` 断言只查存在性，不依赖顺序。
3. **env 显式指定优先级**：若宿主环境设了 AGENTFLOW_SEARCH_BACKEND，resolve 测试需先 delenv 再断言自动路径。

---
_2026-10-05 M6 新增：结构图 + 设计思想 + 成块代码解析（参数逐条表）+ 风险点。_
