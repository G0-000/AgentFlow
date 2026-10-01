# ============================================================================
# AgentFlow · tests/test_sandbox_guard.py —— 沙箱隔离测试（M4）
# 验收点 4：子代理写宿主系统目录被拦 / 沙箱内可写；审计落库。
# ============================================================================
import pytest

from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.sandbox_audit_repositories import SandboxAuditRepository
from agentflow.sandbox import (
    LocalSandbox,
    LocalSandboxProvider,
    NoopSandbox,
    SandboxError,
    SandboxPermissionError,
    get_sandbox_provider,
    reset_sandbox_provider,
    set_sandbox_provider,
)


def test_local_sandbox_write_read_inside(tmp_path):
    """沙箱内文件可写可读（验收点 4：隔离区内正常工作）。"""
    sb = LocalSandbox(tmp_path)
    sb.write_file("note.txt", "hello 沙箱")
    assert sb.read_file("note.txt") == "hello 沙箱"


def test_local_sandbox_rejects_host_path(tmp_path):
    """写沙箱外（宿主）路径被拦截（验收点 4 核心）。"""
    sb = LocalSandbox(tmp_path)
    # /etc 是宿主系统目录，写它必须被拒
    with pytest.raises(SandboxPermissionError):
        sb.write_file("/etc/agentflow_should_not_write.txt", "x")
    # 宿主根下读文件同样被拒
    with pytest.raises(SandboxPermissionError):
        sb.read_file("/etc/hosts")


def test_local_sandbox_rejects_traversal(tmp_path):
    """../ 逃逸路径被规范化后拦截。"""
    sb = LocalSandbox(tmp_path)
    with pytest.raises(SandboxPermissionError):
        sb.write_file(str(tmp_path / ".." / "escape.txt"), "x")


def test_local_sandbox_execute_command_in_root(tmp_path):
    """命令在沙箱根目录执行（cwd=root），echo 正常。"""
    sb = LocalSandbox(tmp_path)
    out = sb.execute_command("echo sandbox-ok", timeout=10)
    assert "sandbox-ok" in out


def test_noop_sandbox_denies_everything():
    """空沙箱：任何操作抛 SandboxError（fail-closed 默认）。"""
    sb = NoopSandbox()
    with pytest.raises(SandboxError):
        sb.execute_command("ls")
    with pytest.raises(SandboxError):
        sb.write_file("x.txt", "y")
    with pytest.raises(SandboxError):
        sb.read_file("x.txt")


def test_local_sandbox_list_dir_depth(tmp_path):
    """list_dir 的 max_depth 语义（检查轮修正：原 rglob 无限递归）。

    depth=1 只列直接子项；depth=2 再下一层；depth=3 才看到第三层。
    """
    sb = LocalSandbox(tmp_path)
    sb.write_file("top.txt", "t")
    sb.write_file("a/one.txt", "1")
    sb.write_file("a/b/two.txt", "2")
    sb.write_file("a/b/c/three.txt", "3")

    l1 = sb.list_dir(".", max_depth=1)
    assert "top.txt" in l1 and "a" in l1
    assert not any(x.startswith("a/") for x in l1)  # 不出现 a/one.txt

    l2 = sb.list_dir(".", max_depth=2)
    assert "a/one.txt" in l2
    assert not any(x.startswith("a/b/") for x in l2)  # 不出现 a/b/two.txt

    l3 = sb.list_dir(".", max_depth=3)
    assert "a/b/two.txt" in l3
    assert "a/b/c/three.txt" not in l3  # 第三层目录内的文件要 depth=4


def test_provider_injection_and_audit(tmp_path):
    """注入 LocalSandboxProvider + 审计记录放行/拦截（验收点 4 配套）。"""
    audit_db = tmp_path / "audit.db"
    conn = init_db(str(audit_db))
    repo = SandboxAuditRepository(conn=conn)

    provider = LocalSandboxProvider(tmp_path / "sandbox-root")
    set_sandbox_provider(provider)
    try:
        sb = get_sandbox_provider().get(get_sandbox_provider().acquire())
        assert sb is not None

        # 放行操作（沙箱内写）
        sb.write_file("a.txt", "内容")
        repo.record(action="write_file", target="a.txt", allowed=True, subagent_name="test")
        # 拦截操作（越界）
        try:
            sb.write_file("/etc/blocked.txt", "x")
        except SandboxPermissionError:
            repo.record(action="write_file", target="/etc/blocked.txt", allowed=False, reason="越界")

        rows = repo.query(limit=10)
        assert len(rows) == 2
        allowed = {r["allowed"] for r in rows}
        assert allowed == {0, 1}  # 既有放行也有拦截记录
        blocked = [r for r in rows if r["allowed"] == 0]
        assert blocked and "/etc/blocked.txt" in blocked[0]["target"]
    finally:
        reset_sandbox_provider()  # 恢复默认，避免影响其他测试
