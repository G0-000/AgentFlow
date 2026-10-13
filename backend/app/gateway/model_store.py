# ============================================================================
# AgentFlow · gateway/model_store.py —— 模型配置 SQLite 存储
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/app/gateway/model_store.py
# 对标来源: evoflow/persistence/model_connections.py + config 的 db 模型表
#   原版模型配置持久化在 SQLite（evoflow_models），面板可增删改、不重启切换。
#   M7 裁剪：只保留"一个对话模型连接"所需字段（对齐 ChatModelConfig）。
# 里程碑: M7（Gateway 核心）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ GATEWAY_MODELS_SQL（建表，幂等 CREATE IF NOT EXISTS）        │
# │   gateway_models:                                          │
# │     name(PK) / provider / base_url / model / api_key       │
# │     / temperature / is_primary / created_at / updated_at   │
# │                                                             │
# │ ModelStore(db_path)                                         │
# │   ensure_table()                ← lifespan 建表（幂等）    │
# │   seed_primary(cfg: ChatModelConfig) ← yaml→SQLite 迁移    │
# │   create(...) / get(name) / list_all()                    │
# │   update(name, **fields) / delete(name)                   │
# │   set_primary(name) / get_primary() → Row|None             │
# │   to_chat_config(row) → ChatModelConfig（喂给模型工厂）     │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 不裸连：一律走 persistence/db.py 的 connect()（统一 WAL/Row/外键），
#    沿用 BaseRepository 的 db_path + 线程本地连接模式（FastAPI 多请求线程安全）。
# 2. 模型配置落库后，runs 每次执行都 get_primary() 现场读取——
#    改 SQLite 即生效，无需重启进程（验收点 4 核心）。
# 3. 表自建在 gateway 包内（CREATE IF NOT EXISTS），不改 persistence/schema.py
#    （域边界：飞书渠道/回归由并行子代理负责，本包自包含）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. ModelStore: 模型配置 SQLite 数据访问
# 🔒 内部私有函数
# 1. _row_to_dict: sqlite3.Row → JSON 友好 dict（api_key 默认打码给前端）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. api_key 入库为明文（本地单机调试）；对外 GET 默认打码，勿在日志打印明文
# 2. is_primary 同一时刻只允许一行=1；set_primary 用事务翻转
# 3. db_path 模式每线程一连接，进程结束不主动 close（WAL 安全）
# ============================================================================

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime

from agentflow.config.model_config import ChatModelConfig
from agentflow.persistence.db import connect

# 模型配置表（gateway 自包含；幂等建表，重复执行不报错）
GATEWAY_MODELS_SQL = """
CREATE TABLE IF NOT EXISTS gateway_models (
    name        TEXT PRIMARY KEY,                 -- 模型唯一标识（如 deepseek-chat / my-glm）
    provider    TEXT NOT NULL DEFAULT 'openai-compatible',  -- 供应商类型（factory 分发依据）
    base_url    TEXT NOT NULL DEFAULT '',        -- API 地址
    model       TEXT NOT NULL DEFAULT '',        -- 真实模型名
    api_key     TEXT NOT NULL DEFAULT '',         -- 密钥（本地明文存储，对外打码）
    temperature REAL NOT NULL DEFAULT 0.3,       -- 采样温度
    is_primary  INTEGER NOT NULL DEFAULT 0,       -- 1=当前 runs 使用的主模型（唯一）
    created_at  TEXT NOT NULL,                    -- 创建时间（UTC ISO）
    updated_at  TEXT NOT NULL                     -- 更新时间
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ModelStore:
    """模型配置 SQLite 存储（db_path + 线程本地连接，对齐 BaseRepository 模式）。

    职责边界:
        - 这里存"可被 API 管理的模型连接配置"（增删改查 + 主模型标记）
        - runs 运行时 get_primary() 现场读取当前主模型 → 不重启切换
        - 不负责真正调用模型（那是 models/factory + lead_agent 的事）
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()

    @property
    def _conn(self) -> sqlite3.Connection:
        """当前线程的连接（每个线程各建一个，SQLite 线程安全标准做法）。"""
        c = getattr(self._local, "conn", None)
        if c is None:
            c = connect(self._db_path)  # 复用 persistence.db 统一配置
            self._local.conn = c
        return c

    # ---------- 建表 / 迁移 ----------
    def ensure_table(self) -> None:
        """建表（幂等）。lifespan 内调用，配合 bootstrap.init_db。"""
        self._conn.executescript(GATEWAY_MODELS_SQL)
        self._conn.commit()

    def seed_primary(self, cfg: ChatModelConfig) -> bool:
        """yaml 既有 chat 配置 → SQLite（幂等：仅当表为空时写入一条主模型）。

        返回:
            True=本次写入了种子；False=表已有模型（跳过，不覆盖用户经 API 建的）
        """
        existing = self._conn.execute("SELECT COUNT(*) FROM gateway_models").fetchone()[
            0
        ]
        if existing:
            return False
        now = _now()
        self._conn.execute(
            "INSERT INTO gateway_models "
            "(name, provider, base_url, model, api_key, temperature, is_primary, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (
                cfg.model or "default",
                cfg.provider,
                cfg.base_url,
                cfg.model,
                cfg.api_key,
                cfg.temperature,
                now,
                now,
            ),
        )
        self._conn.commit()
        return True

    # ---------- CRUD ----------
    def create(
        self,
        name: str,
        provider: str = "openai-compatible",
        base_url: str = "",
        model: str = "",
        api_key: str = "",
        temperature: float = 0.3,
        make_primary: bool = False,
    ) -> sqlite3.Row:
        """新增一条模型配置。已存在同名则 raise ValueError。"""
        if self.get(name) is not None:
            raise ValueError(f"模型已存在: {name}")
        now = _now()
        # 首个模型自动设为主模型（开箱即用，避免 runs 找不到主模型）
        count = self._conn.execute("SELECT COUNT(*) FROM gateway_models").fetchone()[0]
        primary = 1 if (make_primary or count == 0) else 0
        if primary:
            self._conn.execute("UPDATE gateway_models SET is_primary = 0")
        self._conn.execute(
            "INSERT INTO gateway_models "
            "(name, provider, base_url, model, api_key, temperature, is_primary, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, provider, base_url, model, api_key, temperature, primary, now, now),
        )
        self._conn.commit()
        return self.get(name)  # type: ignore[return-value]

    def get(self, name: str) -> sqlite3.Row | None:
        """按 name 取一行。"""
        return self._conn.execute(
            "SELECT * FROM gateway_models WHERE name = ?", (name,)
        ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        """列出全部模型（主模型排最前，其次按创建时间）。"""
        return self._conn.execute(
            "SELECT * FROM gateway_models ORDER BY is_primary DESC, created_at ASC"
        ).fetchall()

    def update(self, name: str, **fields: object) -> sqlite3.Row:
        """局部更新（PATCH）。只更新传入的字段；不存在则 raise ValueError。"""
        if self.get(name) is None:
            raise ValueError(f"模型不存在: {name}")
        allowed = {"provider", "base_url", "model", "api_key", "temperature"}
        sets = [f"{k} = ?" for k in fields if k in allowed]
        if not sets:
            return self.get(name)  # type: ignore[return-value]
        params = [fields[k] for k in fields if k in allowed]
        params.append(_now())
        params.append(name)
        self._conn.execute(
            f"UPDATE gateway_models SET {', '.join(sets)}, updated_at = ? WHERE name = ?",
            tuple(params),
        )
        self._conn.commit()
        return self.get(name)  # type: ignore[return-value]

    def delete(self, name: str) -> None:
        """删除一行；若删的是主模型，把剩余第一行提为主模型。"""
        if self.get(name) is None:
            raise ValueError(f"模型不存在: {name}")
        self._conn.execute("DELETE FROM gateway_models WHERE name = ?", (name,))
        # 被删的是主模型 → 提一个替补，避免 runs 找不到主模型
        row = self._conn.execute(
            "SELECT name FROM gateway_models ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row:
            self._conn.execute(
                "UPDATE gateway_models SET is_primary = 1 WHERE name = ?",
                (row["name"],),
            )
        self._conn.commit()

    # ---------- 主模型 ----------
    def set_primary(self, name: str) -> None:
        """把某模型设为主模型（其他全部置 0）。不存在则 raise ValueError。"""
        if self.get(name) is None:
            raise ValueError(f"模型不存在: {name}")
        self._conn.execute("UPDATE gateway_models SET is_primary = 0")
        self._conn.execute(
            "UPDATE gateway_models SET is_primary = 1 WHERE name = ?", (name,)
        )
        self._conn.commit()

    def get_primary(self) -> sqlite3.Row | None:
        """取当前主模型行；无标记主模型时回退到第一行。"""
        row = self._conn.execute(
            "SELECT * FROM gateway_models WHERE is_primary = 1 LIMIT 1"
        ).fetchone()
        if row is not None:
            return row
        return self._conn.execute(
            "SELECT * FROM gateway_models ORDER BY created_at ASC LIMIT 1"
        ).fetchone()

    # ---------- 转换 ----------
    @staticmethod
    def to_chat_config(row: sqlite3.Row) -> ChatModelConfig:
        """把存储行转成 ChatModelConfig（喂给 models/factory.create_chat_model）。"""
        return ChatModelConfig(
            provider=row["provider"],
            base_url=row["base_url"],
            model=row["model"],
            api_key=row["api_key"],
            temperature=row["temperature"],
        )

    @staticmethod
    def to_dict(row: sqlite3.Row, *, mask_key: bool = True) -> dict:
        """序列化为 JSON 友好 dict。api_key 默认打码（****末4位）。"""
        api_key = row["api_key"] or ""
        if mask_key and api_key:
            api_key = f"****{api_key[-4:]}" if len(api_key) > 4 else "****"
        return {
            "name": row["name"],
            "provider": row["provider"],
            "base_url": row["base_url"],
            "model": row["model"],
            "api_key": api_key,
            "temperature": row["temperature"],
            "is_primary": bool(row["is_primary"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
