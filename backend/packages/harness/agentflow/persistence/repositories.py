# ============================================================================
# AgentFlow · persistence/repositories.py —— Repository 基类
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/repositories.py
# 对标来源: evoflow/persistence/xxx_repositories.py
#   原版每张表一个 repo 文件；M1 用基类 + 子类模式起步。
# 里程碑: M1
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────┐
# │ BaseRepository（抽象基类）                    │
# │   └─ 约束子类实现 4 个方法:                   │
# │      table_name / create / get / delete      │
# │   _execute(...) 统一执行 SQL + commit        │
# │      （所有写操作都 commit，读操作不 commit） │
# │   _fetch_one / _fetch_all 统一查询           │
# │                                              │
# │ 使用方: SessionRepository（session_          │
# │         repositories.py）                    │
# └──────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 基类收拢"执行 SQL + commit + 查询"样板，子类只写业务 SQL。
# 2. 写操作统一 commit：漏 commit 是 SQLite 最常见 bug，集中处理。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. BaseRepository: 数据访问基类（抽象）
# 🔒 内部私有函数
# 1. _execute: 执行写 SQL + commit
# 2. _fetch_one / _fetch_all: 统一查询
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 抽象方法未实现时子类实例化报错（ABC 机制），勿删 abstractmethod
# 2. _execute 默认 commit；只读操作别用它（避免无谓写）
# ============================================================================

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """数据访问基类：统一 SQL 执行入口。

    为什么要有基类:
        1. 每个 repo 不重复写 conn.execute + commit 的样板
        2. 统一约定"写操作 commit / 读操作不 commit"
        3. 后续 audit（M4 沙箱审计表）可在此加统一钩子
    """

    def __init__(self, conn: sqlite3.Connection):
        """注入连接（由调用方创建并持有）。"""
        self.conn = conn

    @property
    @abstractmethod
    def table_name(self) -> str:
        """子类声明自己管理哪张表。"""

    # ---- 统一执行器 ----
    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL 并提交（只用于写操作）。"""
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def _fetch_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """查询单行（不提交——读操作不写库）。"""
        return self.conn.execute(sql, params).fetchone()

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """查询多行（不提交）。"""
        return self.conn.execute(sql, params).fetchall()

    # ---- 子类必须实现的 CRUD ----
    @abstractmethod
    def create(self, **kwargs): ...  # 新增一行（子类如 SessionRepository.create）

    @abstractmethod
    def get(self, row_id: str) -> sqlite3.Row | None: ...  # 按主键取一行

    @abstractmethod
    def delete(self, row_id: str) -> None: ...  # 按主键删除
