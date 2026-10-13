# ============================================================================
# AgentFlow · runtime/long_run_limits.py —— 长任务时长 / 递归预算常量
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【结构图】
# ┌──────────────────────────────────────────────────────────────────────┐
# │ 模块级常量（import 时即固定求值，env 覆盖一次读取）：                 │
# │   LONG_RUN_WALL_SECONDS        墙钟总预算（默认 4h）                │
# │   LONG_RUN_WALL_MS              = 上者 * 1000                        │
# │   LONG_RUN_STREAM_READ_SECONDS 流式读取上限（默认=墙钟）            │
# │   LONG_RUN_RECURSION_LIMIT      主图 super-step 上限（默认 7500）    │
# │   MAX_SUBAGENT_RECURSION_LIMIT  子图递归上限（默认 9000）            │
# │ 函数：httpx_stream_timeout() → httpx.Timeout（流式 read 覆盖全程）  │
# └──────────────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【设计思想】
# 长 Plan / supervisor 运行可能持续数小时：墙钟预算、流式读取超时、图递归上限
# 三处必须对齐，否则长任务会被 read timeout 或 recursion limit 中途杀掉。
# 所有阈值都可用环境变量覆盖；环境变量前缀用 AGENTFLOW_（原版为 EVOFLOW_）。
# ----------------------------------------------------------------------------
# 🎯 【实用场景】
# 1. 主图编译 / checkpointer 配置处读 LONG_RUN_RECURSION_LIMIT。
# 2. httpx 客户端拉 LangGraph /runs/stream 时用 httpx_stream_timeout()。
# ----------------------------------------------------------------------------
# 📊 【顺序执行链流程图】
# import 本模块 → 读 env（AGENTFLOW_LONG_RUN_WALL_SECONDS 等）
#   → max(下限, int(...)) 钳制 → 常量固定
# 调用 httpx_stream_timeout() → import httpx → 按 read/write/pool 组装 Timeout
# ----------------------------------------------------------------------------
# 🧩 【代码解析】
# - 每个常量都带下限钳制（max(...)）：防止 env 配成过小值把长任务误杀。
# - httpx_stream_timeout 内部才 import httpx：纯核心单测不依赖 httpx 即可 import 本模块。
# ----------------------------------------------------------------------------
# ❓ Q&A
# Q: 为什么 write 超时是 read 的一半且至少 600s？
# A: 流式请求主要时间在 read（等模型出块），write 只是发请求，取一半足够，
#    但保底 600s 防止慢网络下大 body 发送被误判超时。
# ----------------------------------------------------------------------------
# ⚠️ 【风险点】
# 1. 改默认墙钟值必须三处（常量 / 流式 read / 注释）一起改，否则超时不一致。
# 2. env 变量前缀是 AGENTFLOW_，勿写成 EVOFLOW_（那是原版变量名，见下行注释）。
#
# 页脚：2026-10-13（移植自 evoflow/runtime/long_run_limits.py）
# ============================================================================

"""Plan / supervisor 长运行共享的墙钟与 LangGraph 递归预算。

环境变量前缀 ``AGENTFLOW_``（原版对应变量名见各常量注释，为 EVOFLOW_ 前缀）。
"""

from __future__ import annotations

import os

# 默认 4h —— 对齐 project crew / gateway stream proxy / guardian hold / panel chat。
# 原版 env：EVOFLOW_LONG_RUN_WALL_SECONDS
LONG_RUN_WALL_SECONDS = max(3600, int(os.getenv("AGENTFLOW_LONG_RUN_WALL_SECONDS", "14400")))

LONG_RUN_WALL_MS = LONG_RUN_WALL_SECONDS * 1000

# 原版 env：EVOFLOW_LONG_RUN_STREAM_READ_SECONDS
LONG_RUN_STREAM_READ_SECONDS = float(
    os.getenv("AGENTFLOW_LONG_RUN_STREAM_READ_SECONDS", str(LONG_RUN_WALL_SECONDS))
)

# Lead / Plan 主图 super-step 上限（不是 LLM turn 数）。
# 原版 env：EVOFLOW_LONG_RUN_RECURSION_LIMIT
LONG_RUN_RECURSION_LIMIT = max(500, int(os.getenv("AGENTFLOW_LONG_RUN_RECURSION_LIMIT", "7500")))

# 子代理图：未显式设置时由 max_turns 推导；长项目角色的上限。
# 原版 env：EVOFLOW_SUBAGENT_RECURSION_LIMIT_MAX
MAX_SUBAGENT_RECURSION_LIMIT = max(
    1500,
    int(os.getenv("AGENTFLOW_SUBAGENT_RECURSION_LIMIT_MAX", "9000")),
)


def httpx_stream_timeout():
    """LangGraph ``/runs/stream`` 的 httpx 客户端超时（read 需覆盖整个 Plan 执行）。"""
    import httpx

    read_s = LONG_RUN_STREAM_READ_SECONDS
    write_s = min(read_s, max(600.0, read_s / 2.0))
    return httpx.Timeout(connect=10.0, read=read_s, write=write_s, pool=120.0)
