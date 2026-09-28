# ============================================================================
# AgentFlow · config/paths.py —— 数据路径定位
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/config/paths.py
# 仿原: evoflow/config/paths.py
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌────────────────────────────────────────────────────────┐
# │ 目录层级（从本文件向上数）:                             │
# │   parents[0] agentflow/config                          │
# │   parents[1] agentflow                                 │
# │   parents[2] harness                                   │
# │   parents[3] packages                                  │
# │   parents[4] backend                                   │
# │   parents[5] AgentFlow  ← 项目根 (PROJECT_ROOT)         │
# │                                                        │
# │  default_data_dir() → 项目根/data                      │
# │  default_db_path()  → 项目根/data/agentflow.db         │
# └────────────────────────────────────────────────────────┘
# 设计动机: 用 __file__ 定位（而非 os.getcwd()），保证从任何
# 目录启动都能找到 data/ 与数据库，不依赖"先 cd 到项目根"。
# ============================================================================
from __future__ import annotations

from pathlib import Path

# 项目根：AgentFlow/（从本文件所在位置向上 5 级）
PROJECT_ROOT = Path(__file__).resolve().parents[5]
# 后端根：backend/
BACKEND_ROOT = Path(__file__).resolve().parents[4]


def default_data_dir() -> str:
    """数据目录：项目根/data（SQLite、日志等落盘位置）。"""
    return str(PROJECT_ROOT / "data")


def default_db_path() -> str:
    """SQLite 文件路径：项目根/data/agentflow.db。"""
    return str(Path(default_data_dir()) / "agentflow.db")
