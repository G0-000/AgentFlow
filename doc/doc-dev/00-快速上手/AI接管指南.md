<!-- ============================================================
  AgentFlow doc · 文档注释
  更新时间: 2026-09-28
  维护约定: 本文件内容随里程碑推进更新；接手 AI 先读标题与正文引言。
  关联项目: AgentFlow（仿写 EvoFlow，原版参照 /Users/main/EvoFlow 只读）
================================================================ -->
# 给接手 AI 的快速指南（AI 接管指南）

> **如果你是刚接手 AgentFlow 项目的 AI（无论哪个平台）**：照本文档执行，5 分钟内了解项目、验证环境、找到下一步。

## 0. 项目是什么（一句话）

AgentFlow 是**仿写 EvoFlow**（LangGraph 驱动的长任务 Agent 运行时）的独立项目——不是 fork，是从 0 按原版架构思想重写。**原版参照在 `/Users/main/EvoFlow`（只读对照，不要改）**。

## 1. 第一件事：读这些文档（按序）

| 顺序 | 文档 | 获得什么 |
|---|---|---|
| 1 | [../README.md](../README.md) | 文档地图 + 里程碑进度 |
| 2 | [../02-架构设计/总体设计.md](../02-架构设计/总体设计.md) | 系统设计（三层/数据流/核心概念） |
| 3 | [../02-架构设计/目录结构.md](../02-架构设计/目录结构.md) | 代码在哪 |
| 4 | [../05-验收体系/README.md](../05-验收体系/README.md) | 验收方法论 + 当前状态 |
| 5 | [../06-问题日志/问题日志.md](../06-问题日志/问题日志.md) | 已知坑（先查再动手） |

## 2. 环境验证（2 分钟）

```bash
cd /Users/main/AgentFlow/backend
export PATH="$HOME/.local/bin:$PATH"   # uv 在 ~/.local/bin
uv sync                                # 应无报错（已锁定版本）
uv run python -c "import agentflow; print('OK', agentflow.__version__)"
```

## 3. 当前状态（接手时核对）

- **M0**：✅ 环境通（uv/pnpm/双包 workspace）
- **M1**：🟡 代码完成（20 文件），差 `.env` 真实 key 跑通对话（见 [M1-验收清单](../05-验收体系/M1-验收清单.md)）
- **M2-M8**：⏳ 未开始（验收清单已全部建好，见 [05-验收体系](../05-验收体系/)）

## 4. 硬性约定（违反会导致返工）

1. **架构规则 R1**：`agentflow/`（核心层）不得 import `app/*`（应用层）；反向能力走端口，M7 才有应用层
2. **SQLite 唯一属主**：所有 SQL 收口 `agentflow/persistence/`，其他模块不直接碰 DB
3. **目录照搬原版**：新模块先看原版 `EvoFlow/backend/packages/harness/evoflow/` 对应目录，文件命名对齐（`xxx_tool.py` / `xxx_repositories.py`）
4. **依赖版本先查原版 lock**：`/Users/main/EvoFlow/backend/uv.lock`——遇到版本问题不要自己猜（见 ADR-002）
5. **config.yaml 不写密钥**：密钥放 `.env`，配置里用 `${ENV}` 占位
6. **每里程碑先建验收清单再动手**（模板：05-验收体系/M2-验收清单.md 格式）

## 5. 常用命令速查

| 命令（backend/ 下） | 用途 |
|---|---|
| `uv sync` | 装/更新依赖（按 pyproject + lock） |
| `uv run agentflow` | 启动终端对话（M1 验收入口） |
| `uv run agentflow --thread <id>` | 复用会话（验证持久化） |
| `uv run pytest tests/` | 跑测试 |
| `uv run ruff check .` | lint |
| `uv run python -c "..."` | 快速验证代码 |

## 6. 接手后第一步

先完成 **M1 剩余验收**（填 `.env` key → 跑 `uv run agentflow` → 完成"真实对话 + 持久化"2 项），
然后把 [../05-验收体系/M2-验收清单.md](../05-验收体系/M2-验收清单.md) 转成实际代码（工具目录 + 流式）。
