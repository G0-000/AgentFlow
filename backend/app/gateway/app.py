# ============================================================================
# AgentFlow · gateway/app.py —— FastAPI 应用装配（create_app 工厂）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/app/gateway/app.py
# 对标来源: evoflow/gateway/app.py（裁剪：原版含大量后台预热/中间件/诊断）
#   M7 只做：init_db + 模型表迁移 + 挂 3 个 router + 健康检查。
# 里程碑: M7（Gateway 核心）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ create_app(db_path?, runner?, config?) → FastAPI              │
# │   lifespan:                                                  │
# │     ① init_db(db_path)            ← 复用 persistence.bootstrap│
# │     ② ModelStore.ensure_table()   ← gateway_models 幂等建表  │
# │     ③ config.models → seed_primary()  ← yaml→SQLite 迁移(幂等)│
# │   app.state: db_path / model_store / sessions / runs / runner│
# │   mount: models.router / runs.router / threads.router (/api) │
# │   GET /health → {"status":"ok"}                              │
# │                                                              │
# │ create_default_app() → 加载 .env + config.yaml 后 create_app │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 工厂注入：create_app(db_path=tmp) 让测试用临时库；runner=fake 让测试离线。
# 2. lifespan 做一次性初始化（建表 + yaml 模型迁移），迁移幂等（表空才种子）。
# 3. 默认 runner 在调用时才读 ModelStore.get_primary() → 改 SQLite 不重启即切换。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. create_app: 应用工厂（测试/生产共用）
# 2. create_default_app: 生产装配（加载配置后建 app）
# 🔒 内部私有函数
# 1. _build_default_runner: 装真 agent 的 runner（读现场主模型）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 不要在模块层执行 create_default_app()——测试 import 本模块会触发副作用
# 2. uvicorn 入口用 --factory app.gateway.app:create_default_app
# 3. 默认 runner 是缓冲式（invoke 完才出块）；真流式后续在 _build_default_runner 增强
# ============================================================================

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from agentflow.config.app_config import AppConfig, load_config
from agentflow.config.model_config import ModelConfig  # noqa: F401  (类型标注用)
from agentflow.config.paths import PROJECT_ROOT, default_db_path
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.session_repositories import SessionRepository
from agentflow.webui.auth import hash_password
from fastapi import FastAPI

from app.gateway.model_store import ModelStore
from app.gateway.routers import auth as auth_router
from app.gateway.routers import models as models_router
from app.gateway.routers import runs as runs_router
from app.gateway.routers import threads as threads_router

logger = logging.getLogger(__name__)


def _build_default_runner(db_path: str, model_store: ModelStore):
    """构造默认 runner：每次调用现场读主模型 → 真 agent 对话。

    返回 async(thread_id, message) -> AsyncIterator[str]。
    测试注入 fake runner 时本函数不会被用到（全程离线）。
    """

    async def runner(thread_id: str, message: str) -> AsyncIterator[str]:
        import anyio
        from agentflow.agents.checkpointer.provider import create_sqlite_checkpointer
        from agentflow.agents.lead_agent.agent import make_lead_agent
        from agentflow.models.factory import create_chat_model
        from langchain_core.messages import HumanMessage

        row = model_store.get_primary()
        if row is None:
            raise RuntimeError("未配置任何模型，请先 POST /api/models 添加")
        cfg = ModelStore.to_chat_config(row)
        model = create_chat_model(cfg)
        checkpointer = create_sqlite_checkpointer(db_path)
        agent = make_lead_agent(
            model=model, checkpointer=checkpointer, tools=[], middlewares=[]
        )

        def _invoke() -> str:
            resp = agent.invoke(
                {"messages": [HumanMessage(content=message)]},
                config={"configurable": {"thread_id": thread_id}},
            )
            msgs = (
                resp.get("messages")
                if isinstance(resp, dict)
                else getattr(resp, "messages", [])
            )
            return msgs[-1].content if msgs else ""

        # 同步 agent.invoke 放线程池跑，避免阻塞事件循环（M7 缓冲式，非逐 token 流）
        text = await anyio.to_thread.run_sync(_invoke)
        yield text

    return runner


def create_app(
    db_path: str | None = None,
    runner=None,
    config: AppConfig | None = None,
    auth_config: dict | None = None,
) -> FastAPI:
    """创建 FastAPI 应用。

    参数:
        db_path: SQLite 路径；缺省 default_db_path()。测试传临时库。
        runner: 注入的执行体 async(thread_id, message)->AsyncIterator[str]；
                缺省装真 agent。测试传 fake → 离线。
        config: 应用配置（含 models 时做 yaml→SQLite 迁移）；缺省不迁移。
        auth_config: 登录配置 dict（M8：{username, password_hash, jwt_secret}）。
                由 create_default_app 从 config.yaml 的 auth 段装配；
                测试不传 → /api/auth/login 返回 503（未配置）。
    """
    db_path = db_path or default_db_path()

    # R1：把应用层适配器装进核心 runtime 端口（幂等；当前无真实适配器，仅占位）。
    # 放在工厂开头：无论 lifespan 是否被测试触发，端口装配都执行一次。
    from app.gateway.runtime_adapters import register_runtime_adapters

    register_runtime_adapters()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ① 建业务表（sessions/messages/...，复用现有 bootstrap，幂等）
        init_db(db_path)
        # ② gateway 模型表（自包含建表，幂等）
        store: ModelStore = app.state.model_store
        store.ensure_table()
        # ③ yaml 既有配置 → SQLite（仅表空时种子，幂等，不覆盖 API 建的模型）
        if config is not None and config.models is not None:
            store.seed_primary(config.models.chat)
        yield

    app = FastAPI(
        title="AgentFlow Gateway",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
    )

    # 装配 app.state（依赖注入落点）
    app.state.db_path = db_path
    app.state.model_store = ModelStore(db_path=db_path)
    app.state.sessions = SessionRepository(db_path=db_path)
    app.state.runs = {}  # run_id -> run record（进程内执行态）
    app.state.runner = runner or _build_default_runner(db_path, app.state.model_store)
    app.state.auth_config = auth_config  # M8 登录配置（None → login 返回 503）

    # 挂 4 个 router（前缀已在各 router 内定义为 /api）
    app.include_router(models_router.router)
    app.include_router(runs_router.router)
    app.include_router(threads_router.router)
    app.include_router(auth_router.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "db_path": db_path}

    return app


def create_default_app() -> FastAPI:
    """生产入口：加载项目根 .env + config.yaml 后建 app（uvicorn --factory 用）。"""
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except Exception:
        logger.debug("dotenv load skipped", exc_info=True)
    cfg = load_config(str(PROJECT_ROOT / "config.yaml"))
    return create_app(config=cfg, auth_config=_load_auth_config())


def _load_auth_config() -> dict | None:
    """从 config.yaml 的 auth 段装配登录配置（M8）。

    学习版：明文密码启动时哈希一次（不落盘）；生产应预存 hash_password 结果。
    auth 段缺失/格式错 → 返回 None（/api/auth/login 将返回 503 诚实报错）。
    """
    try:
        import yaml

        with open(PROJECT_ROOT / "config.yaml", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        raw_auth = raw.get("auth")
        if not isinstance(raw_auth, dict):
            return None
        username = str(raw_auth.get("username") or "").strip()
        password = str(raw_auth.get("password") or "")
        if not username or not password:
            return None
        return {
            "username": username,
            "password_hash": hash_password(password),
            "jwt_secret": str(raw_auth.get("jwt_secret") or "agentflow-m8-dev-secret"),
        }
    except Exception:
        logger.warning("auth config read failed; /api/auth/login disabled", exc_info=True)
        return None
