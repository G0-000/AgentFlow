# ============================================================================
# AgentFlow · mcp/client.py —— MCP 外部服务器接入：服务器参数构建（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/mcp/client.py
# 对标来源: evoflow/mcp/client.py（79 行，几乎原样学）
#   裁剪：去掉原版 ExtensionsConfig/SQLite 配置读取，改用 agentflow 的 McpServerConfig（D2）。
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ McpServerConfig                                            │
# │   (name/transport/command/args/env/url/headers)            │
# │            ↓ build_server_params(server_name, config)      │
# │ langchain-mcp-adapters 的服务器参数字典:                    │
# │   stdio: {"transport":"stdio","command":...,"args":...,    │
# │           "env":{...}}                                     │
# │   sse/http: {"transport":"sse|http","url":...,             │
# │              "headers":{...}}                              │
# │            ↓ build_servers_config(configs)                 │
# │ {"my-server": {参数字典}, ...}   → MultiServerMCPClient    │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. langchain-mcp-adapters 是官方 MCP 客户端桥接库：给它"服务器名→参数"字典，
#    它负责连接 + 把 MCP 工具转成 BaseTool。本文件只负责"配置 → 参数字典"。
# 2. 三传输参数差异显式化：stdio 要 command/args/env；sse/http 要 url/headers。
# 3. stdio 不转发 timeout/cwd（部分 adapter 版本对未知 kwargs 报错，原版注释经验）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. build_server_params: 单个配置 → langchain-mcp-adapters 参数字典
# 2. build_servers_config: 配置列表 → 服务器名→参数 映射（喂 MultiServerMCPClient）
# ----------------------------------------------------------------------------

from __future__ import annotations

from typing import Any

from agentflow.config.mcp_config import McpServerConfig


def build_server_params(server_name: str, config: McpServerConfig) -> dict[str, Any]:
    """把单个 McpServerConfig 转成 langchain-mcp-adapters 的服务器参数字典。

    入参:
        server_name: 服务器名（仅用于报错信息定位）。
        config: McpServerConfig（transport/command/args/env/url/headers）。

    返回:
        dict：langchain-mcp-adapters 认可的参数字典，按传输类型不同键集。

    异常:
        ValueError: stdio 缺 command，或 sse/http 缺 url（配置非法时显式报错）。
    """
    transport_type = config.transport or "stdio"
    params: dict[str, Any] = {"transport": transport_type}

    if transport_type == "stdio":
        if not config.command:
            raise ValueError(
                f"MCP server '{server_name}' with stdio transport requires 'command' field"
            )
        params["command"] = config.command
        params["args"] = list(config.args)
        if config.env:
            params["env"] = dict(config.env)
    elif transport_type in ("sse", "http"):
        if not config.url:
            raise ValueError(
                f"MCP server '{server_name}' with {transport_type} transport requires 'url' field"
            )
        params["url"] = config.url
        if config.headers:
            params["headers"] = dict(config.headers)
    else:
        raise ValueError(
            f"MCP server '{server_name}' has unsupported transport type: {transport_type}"
        )
    return params


def build_servers_config(configs: list[McpServerConfig]) -> dict[str, dict[str, Any]]:
    """把配置列表转成"服务器名 → 参数字典"映射（喂 MultiServerMCPClient）。

    入参:
        configs: McpServerConfig 列表（来自 load_mcp_servers，已过滤不可用条目）。

    返回:
        dict：服务器名 → 参数字典；配置非法条目跳过并记录（单条失败不影响整体）。
    """
    servers_config: dict[str, dict[str, Any]] = {}
    for server_config in configs:
        try:
            servers_config[server_config.name] = build_server_params(
                server_config.name, server_config
            )
        except ValueError:
            # 单条配置非法（缺 command/url）不阻断整体——M6 容错哲学
            continue
    return servers_config
