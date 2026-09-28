# config/app_config.py — app_config.py

> **文件路径**: `backend/packages/harness/agentflow/config/app_config.py`
> **目录位置**: config → app_config.py
> **职责**: 全局配置入口

## 📋 结构图

```text
┌──────────────────────────────────────────────────────┐
│ load_config(path?) ──► AppConfig                      │
│   ① 定路径: 参数 > AGENTFLOW_CONFIG_PATH > config.yaml│
│   ② 读 yaml（缺文件则空 dict，不报错）                │
│   ③ log_level ← raw["log_level"]                     │
│   ④ data_dir  ← raw["paths"]["data_dir"]             │
│   ⑤ models    ← models_yaml.load_models_from_yaml()  │
└──────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `AppConfig`

**函数**

- `load_config()`

**常量**

- `DEFAULT_CONFIG_PATH`

## 💡 设计思想

1. 全局配置唯一入口：yaml → 类型化对象（AppConfig）。
2. 文件缺失返回默认不报错（容错设计），由调用方校验——
   CLI 检查 models/api_key，缺失给明确提示。
3. 路径支持参数/环境变量覆盖，M7 gateway 复用同一入口。

## 🎯 实用场景

1. 全局配置入口：CLI/未来 gateway 统一从 config.yaml 加载配置
2. 配置缺失检测：models 段未配/无 API key 时给出明确提示（CLI 启动检查）
3. 多环境切换：改 config.yaml 即可切模型/供应商/数据路径

## ❓ Q&A

**Q: 配置加载失败会怎样？**

A: CLI 提示"缺少模型配置"并退出，不会带着坏配置跑

## ⚠️ 风险点

1. 缺文件不报错是设计（容错），调用方必须自行校验关键字段
2. 默认路径是相对 cwd 的 config.yaml；CLI 已显式传项目根路径（P-014）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：app_config.py 头部注释 + 顶层符号。_
