# ============================================================================
# AgentFlow · mcp/tools.py —— MCP 工具加载：配置 → BaseTool 列表（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/mcp/tools.py
# 对标来源: evoflow/mcp/tools.py（366 行裁剪：去掉 SQLite 配置表/指纹/多格式兼容，
#   只留"从 config.yaml 加载 → MultiServerMCPClient → BaseTool[] 同步桥接"主线）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ load_mcp_tools(cfg)                                        │
# │   │                                                       │
# │   ├─ load_mcp_servers(cfg) → [McpServerConfig]            │
# │   │     空列表 → return []（无 MCP 配置就不折腾）          │
# │   ├─ build_servers_config → {name: params}                │
# │   ├─ MultiServerMCPClient(servers)  ← langchain-mcp-adapters│
# │   ├─ client.get_tools()  (async)                          │
# │   └─ asyncio.run(...) 同步桥接 → list[BaseTool]           │
# │   │                                                       │
# │   异常兜底 → return []（MCP 连接失败不影响主 Agent 启动）  │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. MCP 工具是"可选项"：连接失败/配置为空一律返回 []，绝不阻断主 Agent 装配
#    （CLI 无 MCP 服务器时照常对话）。
# 2. asyncio.run 同步桥接：langchain-mcp-adapters 是 async API，agentflow 装配是
#    同步链，桥接一层即可（CLI 单线程场景无事件循环冲突）。
# 3. 懒加载：只有在调用 load_mcp_tools 时才建客户端（不常驻连接）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. load_mcp_tools: 从 AppConfig 加载 MCP 服务器并返回 BaseTool 列表
# ----------------------------------------------------------------------------

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentflow.config.app_config import AppConfig
from agentflow.config.mcp_config import load_mcp_servers
from agentflow.mcp.client import build_servers_config

logger = logging.getLogger(__name__)


def load_mcp_tools(cfg: AppConfig | None = None) -> list[Any]:
    """从配置加载 MCP 外部服务器，返回它们的工具列表（BaseTool）。

    入参:
        cfg: AppConfig（从 .models 之外读取 mcp_servers 段）。None 时尝试加载默认配置。

    返回:
        list[BaseTool]：所有启用 MCP 服务器的工具合并列表。
        配置为空 / 连接失败 → []（可选项语义，不抛错）。

    流程:
        1. load_mcp_servers → 可用服务器列表（空则 return []）
        2. build_servers_config → 服务器名→参数字典
        3. MultiServerMCPClient 连接 + get_tools()（async，asyncio.run 桥接）
    """
    from agentflow.config.app_config import load_config

    cfg = cfg or load_config()
    servers = load_mcp_servers({"mcp_servers": _raw_mcp_servers(cfg)})
    if not servers:
        return []
    servers_config = build_servers_config(servers)
    if not servers_config:
        return []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        async def _collect() -> list[Any]:
            # langchain-mcp-adapters 0.1.0：MultiServerMCPClient 不可作 context manager，
            # 正确用法 = 直接 get_tools()（0.1.0 起不支持 async with / __aexit__）
            client = MultiServerMCPClient(servers_config)
            return await client.get_tools()

        tools = asyncio.run(_collect())
        logger.info("Loaded %d MCP tool(s) from %d server(s)", len(tools), len(servers_config))
        return tools
    except Exception as exc:  # noqa: BLE001 —— MCP 连接失败可选项降级，不阻断主流程
        logger.warning("MCP tools load failed (skipped): %s", exc)
        return []


def _raw_mcp_servers(cfg: AppConfig) -> list[dict[str, Any]]:
    """从 AppConfig 里取 mcp_servers 原始列表。

    说明: AppConfig 目前无 mcp_servers 字段（M6 暂不侵入主配置），
    这里读取 config.yaml 的 mcp_servers 段作为数据源；
    若未来 AppConfig 增加该字段，直接替换实现即可。
    """
    import os

    import yaml

    path = os.environ.get("AGENTFLOW_CONFIG_PATH") or "config.yaml"
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    entries = raw.get("mcp_servers") or []
    return entries if isinstance(entries, list) else []
