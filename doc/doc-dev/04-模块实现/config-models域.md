<!-- ============================================================
  AgentFlow doc · 文档注释
  更新时间: 2026-09-28
  维护约定: 本文件内容随里程碑推进更新；接手 AI 先读标题与正文引言。
  关联项目: AgentFlow（仿写 EvoFlow，原版参照 /Users/main/EvoFlow 只读）
================================================================ -->
# config 域 + models 域（实现说明）

> 对应原版：`evoflow/config/` + `evoflow/models/`。这两个域回答"配置怎么变成可用的模型"。

## 数据流（一条链）

```
config.yaml
   │  app_config.load_config() 读 yaml
   ▼
AppConfig (dataclass)
   │  models_yaml 解析 models 段 + ${ENV} 展开
   ▼
ModelConfig.chat (ChatModelConfig)
   │  factory.create_chat_model() 按 provider 分发
   ▼
ChatOpenAI（连接 GLM / Ollama / LM Studio）
```

## 文件逐个看

### `config/app_config.py`
- 职责：配置总入口，`load_config(path=None)` 返回 `AppConfig`
- 路径优先级：显式参数 > `AGENTFLOW_CONFIG_PATH` > 默认 `config.yaml`（cwd）
- 仿原版点：原版同样支持环境变量覆盖配置路径（`DEER_FLOW_CONFIG_PATH`）

### `config/model_config.py`
- `ChatModelConfig`：provider / base_url / model / api_key / temperature
- 仿原版点：原版字段更多（use 路径、params、vendor 专属），M1 只留连接必需

### `config/models_yaml.py`
- `_resolve_env("${ZHIPU_API_KEY}")` → 从环境变量取 key，**避免密钥写进 yaml/git**
- `load_models_from_yaml()` 缺省返回 None（cli 会提示配置缺失）

### `config/paths.py`
- `PROJECT_ROOT = Path(__file__).resolve().parents[5]`：从 `agentflow/config/paths.py` 向上 5 级到项目根
- `default_db_path()` = `项目根/data/agentflow.db`

### `models/patched_openai.py`
- `create_openai_compatible_chat(cfg)` → `ChatOpenAI(...)`
- 仿原版点：原版 patched_openai 处理供应商差异（extra body/参数别名/流式格式）；M1 留扩展点

### `models/factory.py`
- `create_chat_model(cfg)` 按 provider 分发；不支持的 provider 抛 `ValueError`
- 仿原版点：原版按 `use` 字段（"包.模块:类"）动态加载任意类——M1 简化为 if/elif，M6 多供应商时再学 use 机制

## 本域扩展点（后续里程碑）

| 里程碑 | 加什么 |
|---|---|
| M3 | embedding 模型配置（知识库向量，provider 分发给 embedding factory） |
| M6 | 多供应商（deepseek/volc/minimax）→ factory 扩展 + patched_* 适配 |
| M7 | 模型配置迁移 SQLite + 页面管理（学原版第二阶段的进化） |
