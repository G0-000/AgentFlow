# tools/tool_catalog.py — tool_catalog.py

> **文件路径**: `backend/packages/harness/agentflow/tools/tool_catalog.py`
> **目录位置**: tools → tool_catalog.py
> **职责**: 工具Tier分层定义与字段增强模块

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ ToolTier: Literal 类型，7 种工具档位静态类型定义             │
│ TOOL_TIER_ORDER: 元组常量，Tier 优先级排序基准               │
│ TOOL_TIER_LABELS_ZH: 档位 → 中文标签映射                     │
│ TOOL_TIER_MAP: M2 本地硬编码 5 个工具的档位                  │
│                                                             │
│ normalize_tool_name(name) → 小写去空格                       │
│ resolve_tool_tier(name) → 查档位（未知 → optional 兜底）     │
│ tool_tier_label_zh(tier) → 中文标签                          │
│ enrich_tool_catalog_fields(doc) → 给工具文档注入 tier 字段   │
│ tier_sort_key(tier) → 排序权重（供 tools.py 排序用）         │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `normalize_tool_name()`
- `resolve_tool_tier()`
- `tool_tier_label_zh()`
- `enrich_tool_catalog_fields()`
- `tier_sort_key()`

## 💡 设计思想

1. 使用 Literal 实现静态类型约束，Pylance 静态校验，限制 tier 只能使用
   7 个指定字符串。
2. 独立维护 TOOL_TIER_ORDER 元组，统一定义优先级顺序，用于全局工具排序。
3. 拆分多个单一职责函数：归一化 / 分层判定 / 中文标注 / 字段增强 / 排序权重，
   便于单独扩展（照原版 tool_catalog.py 的职责拆分）。
4. M2 简化：去掉对 intent_tool_profile 等深层模块的依赖，
   用本地 TOOL_TIER_MAP 硬编码当前 5 个工具的档位。

## 🎯 实用场景

1. 工具分层展示：gateway 返回工具列表时附带 tier 与中文标签（enrich_tool_catalog_fields）
2. 工具排序：tier_sort_key 供 tools.py 按"系统核心→常驻→工作区"排序
3. 新增工具登记：TOOL_TIER_MAP 追加一行即可定义新工具的档位（不登记默认 optional）
4. DB 同步/UI 过滤（原版用途）：后续按 tier 做会话工具勾选、退役工具隐藏

## ❓ Q&A

**Q: tier 排序谁在用？**

A: tools.py 的 _finalize_tool_catalog；CLI 启动信息里按 tier 顺序列工具

**Q: 新增工具不登记会怎样？**

A: resolve_tool_tier 兜底 optional，会排到工具列表最后，但不报错

## ⚠️ 风险点

1. TOOL_TIER_ORDER 元组顺序直接决定工具优先级，禁止随意调整顺序
2. 新增 Tier 枚举值，需要同步更新 TOOL_TIER_ORDER、TOOL_TIER_LABELS_ZH
3. retired 代表退役工具，业务逻辑默认不参与 Agent 调度
4. 新增工具必须同步在 TOOL_TIER_MAP 追加一行，否则默认 optional

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：tool_catalog.py 头部注释 + 顶层符号。_
