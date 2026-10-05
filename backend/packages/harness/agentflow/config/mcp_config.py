# ============================================================================
# AgentFlow · config/mcp_config.py —— MCP 外部服务器配置（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/config/mcp_config.py
# 对标来源: evoflow/config/extensions_config.py（裁剪：只留 McpServerConfig + 加载）
#   原版扩展配置含 SQLite 配置表/环境变量解析/市场；M6 只学 config.yaml 段（D2）。
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ config.yaml 的 mcp_servers 段                                │
# │   - name: my-server                                         │
# │     transport: stdio        # stdio | sse | http            │
# │     command: npx            # stdio 必填                     │
# │     args: ["-y", "@modelcontextprotocol/server-xxx"]        │
# │     env: {...}              # 可选：传给子进程的环境变量      │
# │     url: ...                # sse/http 必填                  │
# │     headers: {...}          # sse/http 可选                 │
# │            ↓ load_mcp_servers(raw)                          │
# │ McpServerConfig(name, transport, command, args, env,        │
# │                 url, headers)                                │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 配置哲学 = config.yaml 单一来源（agentflow 一贯做法），不学原版 SQLite 配置表。
# 2. 三传输：stdio（本地子进程）/ sse / http（远程 URL）——覆盖验收点 1 的本地 stdio 场景。
# 3. 缺省容错：transport 缺省 stdio；缺 command 的 stdio 条目直接丢弃（不抛错，
#    与 M1 load_config 的"文件缺失不抛错"容错哲学一致）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. McpServerConfig: 单个 MCP 服务器配置的数据类
# 2. load_mcp_servers: 从 yaml raw dict 解析出启用服务器列表
# ----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpServerConfig:
    """单个 MCP 外部服务器配置（对应 config.yaml mcp_servers 段的一个条目）。

    字段:
        name (str):         服务器名（工具名前缀，如 mcp_my_server_xxx）
        transport (str):    传输类型 stdio/sse/http，缺省 stdio
        command (str|None): stdio 传输必填：启动子进程的命令（如 npx / uvx）
        args (list[str]):   stdio 传输：命令参数，缺省 []
        env (dict):         stdio 传输：传给子进程的额外环境变量，缺省 {}
        url (str|None):     sse/http 传输必填：服务器 URL
        headers (dict):     sse/http 传输：请求头，缺省 {}
    """

    name: str
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


def load_mcp_servers(raw: dict | None) -> list[McpServerConfig]:
    """从 yaml 的 mcp_servers 段解析出启用服务器列表。

    入参:
        raw: config.yaml 整体 dict（或其 mcp_servers 段）。None/缺段 → 空列表。

    规则:
        - 每个条目必须有非空 name；缺 name 的条目丢弃。
        - transport 缺省 stdio；显式 sse/http 时必须带 url，否则丢弃。
        - stdio 时必须带 command，否则丢弃（缺 command 的 stdio 无法启动子进程）。
        - env/headers/args 缺省为空，保留原样传给 langchain-mcp-adapters。

    返回:
        list[McpServerConfig]：可用服务器列表（可能为空）。
    """
    servers: list[McpServerConfig] = []
    entries = (raw or {}).get("mcp_servers") or []
    if not isinstance(entries, list):
        return servers
    for item in entries:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        transport = str(item.get("transport") or "stdio").strip().lower()
        if transport not in ("stdio", "sse", "http"):
            transport = "stdio"
        cfg = McpServerConfig(
            name=name,
            transport=transport,
            command=_opt_str(item.get("command")),
            args=[str(a) for a in (item.get("args") or [])],
            env=dict(item.get("env") or {}),
            url=_opt_str(item.get("url")),
            headers=dict(item.get("headers") or {}),
        )
        if transport == "stdio":
            if not cfg.command:
                continue  # stdio 缺 command → 不可用，丢弃
        else:
            if not cfg.url:
                continue  # sse/http 缺 url → 不可用，丢弃
        servers.append(cfg)
    return servers


def _opt_str(value: Any) -> str | None:
    """None/空 → None；否则 strip 后的字符串。"""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
