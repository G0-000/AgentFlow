# ============================================================================
# AgentFlow · tests/test_subagent_registry.py —— 子代理注册表测试（M4）
# 验收点 1：子代理注册——get_subagent_config 查表 / list_subagents 枚举。
# ============================================================================
from agentflow.subagents import (
    get_subagent_config,
    get_subagent_names,
    list_subagents,
)
from agentflow.subagents.config import SubagentConfig


def test_get_general_purpose_config():
    """内置通用子代理能查到，字段完整。"""
    cfg = get_subagent_config("general-purpose")
    assert isinstance(cfg, SubagentConfig)
    assert cfg.name == "general-purpose"
    assert cfg.model == "inherit"
    assert cfg.tools is None  # 继承父级全部工具
    assert cfg.max_turns > 0
    assert cfg.timeout_seconds > 0


def test_get_bash_config_whitelist():
    """bash 子代理工具白名单只留 terminal_run（最小权限）。"""
    cfg = get_subagent_config("bash")
    assert cfg is not None
    assert cfg.tools == ["terminal_run"]


def test_get_unknown_config_returns_none():
    """未注册的子代理 → None（dispatch 工具据此给友好提示，不炸）。"""
    assert get_subagent_config("no-such-agent") is None


def test_list_subagents_covers_builtins():
    """内置注册表至少含 general-purpose 与 bash。"""
    names = get_subagent_names()
    assert "general-purpose" in names
    assert "bash" in names
    assert len(list_subagents()) >= 2


def test_default_disallowed_tools_prevent_recursion():
    """默认黑名单排除派发类工具（防子代理再派子代理死循环）。"""
    cfg = get_subagent_config("general-purpose")
    assert "dispatch_subagents" in (cfg.disallowed_tools or [])
    assert "ask_clarification" in (cfg.disallowed_tools or [])
