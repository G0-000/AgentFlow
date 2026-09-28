# ============================================================================
# AgentFlow · config/app_config.py —— 全局配置入口
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/config/app_config.py
# 仿原: evoflow/config/app_config.py（原版为 pydantic + 30+ 配置模块，M1 只留 4 字段）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────────────┐
# │ load_config(path?) ──► AppConfig                      │
# │   ① 定路径: 参数 > AGENTFLOW_CONFIG_PATH > config.yaml│
# │   ② 读 yaml（缺文件则空 dict，不报错）                │
# │   ③ log_level ← raw["log_level"]                     │
# │   ④ data_dir  ← raw["paths"]["data_dir"]             │
# │   ⑤ models    ← models_yaml.load_models_from_yaml()  │
# └──────────────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations  # 延迟求值注解：3.12 下允许"类内引用自身类型"

import os
from dataclasses import dataclass, field

import yaml

# 同域模块（相对导入：models 配置类型 / yaml 解析 / 路径）
from agentflow.config.model_config import ModelConfig
from agentflow.config.models_yaml import load_models_from_yaml
from agentflow.config.paths import default_data_dir

# 默认配置文件路径：项目根 config.yaml（仿原版支持环境变量覆盖路径的思路）
DEFAULT_CONFIG_PATH = "config.yaml"


@dataclass
class AppConfig:
    """应用全局配置（M1 只有 3 个字段）。

    字段:
        log_level (str):   日志级别（debug/info/warning/error），默认 info
        models (ModelConfig|None): 模型配置；config.yaml 没有 models 段时为 None
        data_dir (str):     数据目录（SQLite 等落盘位置），默认取 paths 的定位
    """

    log_level: str = "info"
    models: ModelConfig | None = None
    data_dir: str = field(default_factory=default_data_dir)


def load_config(path: str | None = None) -> AppConfig:
    """加载配置并返回类型化 AppConfig。

    路径优先级（从高到低）:
        1. 显式传入的 path 参数
        2. 环境变量 AGENTFLOW_CONFIG_PATH
        3. 默认的 ./config.yaml（当前工作目录）

    容错: 配置文件不存在时返回全默认配置（不抛错），
    后续使用方（cli）再校验关键字段（如 models.chat.api_key）。
    """
    # ① 确定配置文件路径
    cfg_path = path or os.environ.get("AGENTFLOW_CONFIG_PATH") or DEFAULT_CONFIG_PATH

    # ② 读取 yaml（文件缺失时 raw 保持空 dict）
    raw: dict = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    # ③④⑤ 逐字段装配（缺省都走默认值，保证类型安全）
    cfg = AppConfig(log_level=str(raw.get("log_level", "info")))
    cfg.data_dir = str((raw.get("paths") or {}).get("data_dir") or default_data_dir())
    cfg.models = load_models_from_yaml(raw.get("models"))
    return cfg
