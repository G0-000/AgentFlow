# tests/test_mcp_client.py — test_mcp_client.py

> **文件路径**: `backend/packages/harness/tests/test_mcp_client.py`
> **目录位置**: tests → test_mcp_client.py
> **职责**: MCP 外部服务器接入测试（M6 验收点 1）——配置解析 / 参数构建 / 本地 stdio echo server 工具加载

## 📑 目录

- [📋 结构图](#📋-结构图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🧩 代码解析（成块对照 test_mcp_client.py）](#🧩-代码解析成块对照-test_mcp_clientpy)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图

```text
tests/test_mcp_client.py（7 用例 → 验收点 1：MCP 接入）
├── 配置解析（2）
│   ├── test_load_mcp_servers_stdio              stdio 条目完整解析
│   └── test_load_mcp_servers_sse_and_invalid    sse 解析 + 缺 command/url/name 丢弃
├── 参数构建（4）
│   ├── test_build_server_params_stdio           stdio → command/args/env
│   ├── test_build_server_params_sse_http        sse/http → url/headers
│   ├── test_build_server_params_stdio_missing_command_raises  缺 command → ValueError
│   ├── test_build_server_params_unsupported_transport_raises  未知传输 → ValueError
│   └── test_build_servers_config_skips_invalid_entries  非法条目跳过
└── 工具加载（2）
    ├── test_load_mcp_tools_with_stdio_echo_server  本地 stdio 子进程 → echo 工具出现（核心）
    └── test_load_mcp_tools_empty_config_returns_empty  无配置 → []

被测对象: agentflow/mcp/{client,tools}.py + config/mcp_config.py
```

## 📤 关键导出

无独立导出（测试文件）。覆盖的被测契约：

- `load_mcp_servers`：yaml 段 → McpServerConfig 列表（缺 name/command/url 丢弃）
- `build_server_params`：stdio/sse/http 三传输参数字典；非法配置 ValueError
- `build_servers_config`：多服务器映射，单条失败跳过
- `load_mcp_tools`：配置 → BaseTool 列表（可选项语义，失败返回 []）

## 💡 设计思想

1. **验收点 1 用真 stdio 子进程**：临时目录写 FastMCP echo server 脚本（python 执行），经 langchain-mcp-adapters 连接——证明"外部 MCP 服务器工具进入工具目录"真实可用，不依赖外部网络。
2. **AGENTFLOW_CONFIG_PATH 指向临时 yaml**：测试隔离配置来源，不读项目真实 config.yaml。
3. **非法配置显式测**：缺 command/url/name 的条目被丢弃或抛 ValueError——容错路径与严格路径都有覆盖。
4. **可选项语义**：无 MCP 配置时 load_mcp_tools 返回 []（CLI 无 MCP 服务器照常对话）。

## 🧩 代码解析（成块对照 test_mcp_client.py）

### 块 1：stdio echo server 测试（验收点 1 核心）

```python
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
```

**整块解析**（参数逐条）：

| 步骤 | 动作 | 作用 |
|---|---|---|
| `_write_echo_server(tmp_path)` | 写 FastMCP 脚本（echo 工具） | 本地 MCP 服务器本体（stdio 传输） |
| `yaml_path.write_text(...)` | 写临时 config.yaml | mcp_servers 段：name=echo / stdio / command=当前 python / args=脚本路径 |
| `monkeypatch.setenv("AGENTFLOW_CONFIG_PATH", ...)` | 指配置路径 | load_mcp_tools 读这份临时 yaml，不碰项目真实配置 |
| `load_mcp_tools(AppConfig())` | 加载工具 | 配置 → MultiServerMCPClient → BaseTool 列表 |
| `assert len(tools) >= 1` | 断言工具出现 | 验收点 1：外部 MCP 工具进入工具目录 |
| `assert "echo" in names` | 断言 echo 工具名 | FastMCP `@mcp.tool() def echo` 的函数名出现在工具名 |

**关键细节**：`command` 必须是 `sys.executable`（当前 Python 解释器）——子进程才能 import 到同一环境的 mcp 库。

## ⚠️ 风险点

1. **langchain-mcp-adapters 0.1.0 不可作 context manager**（P-019）：`async with MultiServerMCPClient(...)` 报错，正确用法是直接 `await client.get_tools()`——测试依赖该版本行为。
2. **子进程需同一解释器**：command 用 `sys.executable` 而非裸 `python`，否则 mcp 库可能不在子进程环境。
3. **测试耗时偏长**：stdio 子进程起停有真实 I/O，属验收点 1 的必要代价。

---
_2026-10-05 M6 新增：结构图 + 设计思想 + 成块代码解析（参数逐条表）+ 风险点。_
