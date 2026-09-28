# ============================================================================
# AgentFlow · tools/builtins/fetch_url_tool.py —— 网页抓取工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/fetch_url_tool.py
# 对标来源: evoflow/community/web_fetch/tools.py
#   原版：fetch_url（URL → 可读文本），属于社区工具包；
#   M2 简化：requests 直抓 + 粗清洗，不做 JS 渲染。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ _fetch_text(url, timeout=10) -> str                        │
# │   抓取 URL → 粗清洗（去 script/style/标签）→ 截断 2000 字  │
# │   失败/无 requests → 返回友好提示                          │
# │                                                             │
# │ fetch_url_tool(url) -> str                                 │
# │   @tool("fetch_url", return_direct=True)                   │
# │   空 url → "需要 url 参数"；否则委托 _fetch_text           │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 函数内 import requests：保持模块启动轻量（配合 tools.py 延迟加载）。
# 2. 粗清洗用正则（去 script/style/标签）而非 html2text：
#    M2 最小可行，真实项目应学原版用 html2text/BeautifulSoup（注释已标明）。
# 3. 截断 2000 字：控制回填对话的 token 成本（大页面只取开头）。
# 4. 失败返回友好提示而非抛异常：工具调用不能炸掉 Agent 循环。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. fetch_url_tool: 网页抓取工具（LangChain @tool，注册名 "fetch_url"）
# 🔒 内部私有函数
# 1. _fetch_text: 抓取 + 粗清洗 + 截断的核心实现
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 仅静态页面可用；JS 渲染页抓不到正文（M 后期学原版 browser_tool）
# 2. 截断上限 2000 字是硬限制，影响对话回填长度
# 3. 正则清洗只是粗处理，复杂页面可能残留噪声（升级时换 html2text）
# ============================================================================
from __future__ import annotations

from langchain.tools import tool


def _fetch_text(url: str, timeout: int = 10) -> str:
    """抓取 URL 并返回文本（M2 简化：requests 直抓 + 粗清洗）。

    注意：不做 JS 渲染（浏览器能力 M 后期再学原版 browser_tool）。
    """
    try:
        import requests
    except ImportError:
        return "（requests 未安装，无法抓取）"
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "AgentFlow-M2/0.1"})
        resp.raise_for_status()
        # 粗清洗：去掉 HTML 标签（真实项目应学原版用 html2text / BeautifulSoup）
        import re

        text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", resp.text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2000] or "（页面无可见文本）"
    except Exception as exc:  # noqa: BLE001
        return f"（抓取失败: {type(exc).__name__}: {str(exc)[:120]}）"


_FETCH_URL_DESCRIPTION = """\
网页抓取工具：给定 URL，抓取并返回页面正文文本（最多 2000 字）。
当用户要求"打开这个网页 / 看看这个链接讲了什么 / 抓取 xxx 页面"时使用。
注意: 仅支持静态页面；JS 渲染页面可能抓不到内容。
"""


@tool("fetch_url", description=_FETCH_URL_DESCRIPTION, parse_docstring=False, return_direct=True)
def fetch_url_tool(url: str) -> str:
    """抓取网页正文（使用条件见工具 description）。"""
    if not url:
        return "需要 url 参数"
    return _fetch_text(url)
