# tools/builtins/fetch_url_tool.py — fetch_url_tool.py

> **文件路径**: `backend/packages/harness/agentflow/tools/builtins/fetch_url_tool.py`
> **目录位置**: tools → builtins → fetch_url_tool.py
> **职责**: 网页抓取工具

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ _fetch_text(url, timeout=10) -> str                        │
│   抓取 URL → 粗清洗（去 script/style/标签）→ 截断 2000 字  │
│   失败/无 requests → 返回友好提示                          │
│                                                             │
│ fetch_url_tool(url) -> str                                 │
│   @tool("fetch_url", return_direct=True)                   │
│   空 url → "需要 url 参数"；否则委托 _fetch_text           │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `fetch_url_tool()`

**常量**

- `_FETCH_URL_DESCRIPTION`

## 💡 设计思想

1. 函数内 import requests：保持模块启动轻量（配合 tools.py 延迟加载）。
2. 粗清洗用正则（去 script/style/标签）而非 html2text：
   M2 最小可行，真实项目应学原版用 html2text/BeautifulSoup（注释已标明）。
3. 截断 2000 字：控制回填对话的 token 成本（大页面只取开头）。
4. 失败返回友好提示而非抛异常：工具调用不能炸掉 Agent 循环。

## 🎯 实用场景

1. 网页内容获取：用户给 URL 问内容 → 工具抓取并粗清洗（2000 字上限）
2. 静态页面场景：README/文档页/新闻页等可直接抓取文本
3. 注意：动态渲染页面（JS）抓不到正文，需 M5+ 浏览器工具

## ⚠️ 风险点

1. 仅静态页面可用；JS 渲染页抓不到正文（M 后期学原版 browser_tool）
2. 截断上限 2000 字是硬限制，影响对话回填长度
3. 正则清洗只是粗处理，复杂页面可能残留噪声（升级时换 html2text）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：fetch_url_tool.py 头部注释 + 顶层符号。_
