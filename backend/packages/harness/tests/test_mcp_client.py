# ============================================================================
# AgentFlow · tests/test_mcp_client.py —— MCP 外部服务器接入（M6）
# 验收项：①MCP 接入——本地 stdio MCP 服务工具出现并可调用。
# 参数构建用纯函数直测；工具加载用临时 FastMCP echo server（python 子进程 stdio），
# 不依赖外部网络。
# ============================================================================
import pathlib
import sys
import textwrap

import pytest

from agentflow.config.app_config import AppConfig
from agentflow.config.mcp_config import McpServerConfig, load_mcp_servers
from agentflow.mcp.client import build_server_params, build_servers_config

# ── 配置解析 ──────────────────────────────────────────────


def test_load_mcp_servers_stdio():
    cfg = load_mcp_servers(
        {
            "mcp_servers": [
                {"name": "fs", "command": "npx", "args": ["-y", "x"], "env": {"K": "V"}},
            ]
        }
    )
    assert len(cfg) == 1
    s = cfg[0]
    assert s.name == "fs"
    assert s.transport == "stdio"
    assert s.command == "npx"
    assert s.args == ["-y", "x"]
    assert s.env == {"K": "V"}


def test_load_mcp_servers_sse_and_invalid_entries_dropped():
    cfg = load_mcp_servers(
        {
            "mcp_servers": [
                {"name": "remote", "transport": "sse", "url": "http://x/sse"},
                {"name": "no-command", "transport": "stdio"},  # 缺 command → 丢弃
                {"name": "no-url", "transport": "http"},  # 缺 url → 丢弃
                {"name": ""},  # 缺 name → 丢弃
                "not-a-dict",  # 非 dict → 丢弃
            ]
        }
    )
    assert [s.name for s in cfg] == ["remote"]
    assert cfg[0].transport == "sse"
    assert cfg[0].url == "http://x/sse"


# ── 参数构建 ──────────────────────────────────────────────


def test_build_server_params_stdio():
    params = build_server_params("fs", McpServerConfig(name="fs", command="npx", args=["-y", "x"], env={"K": "V"}))
    assert params["transport"] == "stdio"
    assert params["command"] == "npx"
    assert params["args"] == ["-y", "x"]
    assert params["env"] == {"K": "V"}


def test_build_server_params_sse_http():
    p1 = build_server_params("s", McpServerConfig(name="s", transport="sse", url="http://x/sse", headers={"A": "1"}))
    assert p1["url"] == "http://x/sse"
    assert p1["headers"] == {"A": "1"}
    p2 = build_server_params("h", McpServerConfig(name="h", transport="http", url="http://x"))
    assert p2["transport"] == "http"
    assert "headers" not in p2  # 无 headers 不写键


def test_build_server_params_stdio_missing_command_raises():
    with pytest.raises(ValueError, match="requires 'command'"):
        build_server_params("bad", McpServerConfig(name="bad", transport="stdio"))


def test_build_server_params_unsupported_transport_raises():
    with pytest.raises(ValueError, match="unsupported transport"):
        build_server_params("bad", McpServerConfig(name="bad", transport="udp"))


def test_build_servers_config_skips_invalid_entries():
    configs = [
        McpServerConfig(name="ok", command="npx"),
        McpServerConfig(name="bad", transport="stdio"),  # 缺 command → ValueError 跳过
    ]
    result = build_servers_config(configs)
    assert list(result) == ["ok"]


# ── 验收点 ①：本地 stdio MCP 服务工具加载 ──────────────────


def _write_echo_server(tmp_path: pathlib.Path) -> pathlib.Path:
    """写一个 FastMCP echo server 脚本（stdio 传输，本地子进程）。"""
    script = tmp_path / "mcp_echo_server.py"
    script.write_text(
        textwrap.dedent(
            """\
            from mcp.server.fastmcp import FastMCP

            mcp = FastMCP("echo-server")

            @mcp.tool()
            def echo(text: str) -> str:
                \"\"\"把输入原样返回。\"\"\"
                return "echo:" + text

            if __name__ == "__main__":
                mcp.run()
            """
        ),
        encoding="utf-8",
    )
    return script


def test_load_mcp_tools_with_stdio_echo_server(tmp_path, monkeypatch):
    script = _write_echo_server(tmp_path)
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        f"mcp_servers:\n  - name: echo\n    transport: stdio\n    command: {sys.executable}\n    args: [{str(script)!r}]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENTFLOW_CONFIG_PATH", str(yaml_path))
    from agentflow.mcp.tools import load_mcp_tools

    tools = load_mcp_tools(AppConfig())
    assert len(tools) >= 1
    names = {t.name for t in tools}
    assert "echo" in names or any("echo" in n for n in names)


def test_load_mcp_tools_empty_config_returns_empty(monkeypatch, tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("log_level: info\n", encoding="utf-8")
    monkeypatch.setenv("AGENTFLOW_CONFIG_PATH", str(yaml_path))
    from agentflow.mcp.tools import load_mcp_tools

    assert load_mcp_tools(AppConfig()) == []
