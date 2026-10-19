# evopanel/src/pages/models.js — models.js（模型设置页）

> **文件路径**: `evopanel/src/pages/models.js`
> **对标来源**: `EvoFlow/evopanel/src/pages/models.js`（4252 行，含服务商管理/远程模型/上下文预设；学习版裁剪为列表 + 增改删 + 设默认）
> **里程碑**: M8

## 📑 目录

- [📋 结构图 / 思维图](#📋-结构图--思维图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🎯 实用场景](#🎯-实用场景)
- [🧩 顺序执行链](#🧩-顺序执行链)
- [❓ Q&A](#❓-qa)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图 / 思维图

```text
renderModels(container) → 工具栏(+新增) + 模型表格

refresh()   modelsApi.list() → 表格行（名称/服务商/模型/base_url/temp/状态/操作）
openForm(existing?)  showModal 表单（新增/编辑共用）
行内操作：设默认(PATCH is_primary) / 编辑(openForm) / 删除(showConfirm)
```

## 📤 关键导出

- `renderModels(container)` — 渲染模型设置页

## 💡 设计思想

1. **数据面 = M7 gateway models API**（SQLite gateway_models 表）：列表/增/改/删/设默认全走 `modelsApi`——模型存 SQLite 而非 config.yaml，页面改完"不重启代码，下次对话用新模型"（默认 runner 每次调用现场读主模型）。
2. **设默认 = PATCH is_primary:true**：后端 `set_primary` 用事务翻转唯一主模型；前端无需理解 SQL。
3. **新增/编辑共用表单**：编辑时 name 字段 disabled（唯一标识不可改）；api_key 留空 = 不变（PATCH 语义，删除 key 字段）。
4. **弹窗复用 modal.js**：删除确认用 `showConfirm`，表单用 `showModal`——统一交互、可样式化。

## 🎯 实用场景

1. 验收点 4（模型设置）：页面里增一个模型并设默认 → 不重启代码，下次对话用新模型。
2. 学习 M7 ModelStore 的路由面：PATCH/DELETE 的 409/404 语义、主模型事务翻转。

## 🧩 顺序执行链

```text
renderModels(container) → refresh()
  ▼ 步骤 1：modelsApi.list() → GET /api/models
  ├─ 空 → "还没有模型"占位行
  └─ 有 → 步骤 2：逐行渲染表格（escapeHtml 转义）
         ▼ 步骤 3：行内操作绑定
         ├─ 设默认 → modelsApi.update(name, {is_primary:true}) → refresh()
         ├─ 编辑   → openForm(model) → showModal 表单 → 保存 → update(name, body) → refresh()
         └─ 删除   → showConfirm → modelsApi.remove(name) → refresh()
```

## ❓ Q&A / 知识点

**Q: 编辑时为什么 api_key 输入框显示的是打码值？**
A: 后端 `to_dict` 返回打码 api_key（`****WrF8`）；编辑时若留空，前端 `delete body.api_key` → PATCH 不含该字段 → 后端不改（白名单不收 None）。要换 key 就输入新值。

**Q: 新增模型时 is_primary 勾选和"设默认"按钮有什么不同？**
A: 新增勾选 → POST body 带 `is_primary:true`（创建即主）；行内"设默认" → PATCH `{is_primary:true}`（后端事务翻转：旧主降级 + 新主升级）。语义都是"设为唯一主模型"。

**Q: 为什么 provider 默认 `openai-compatible`？**
A: 学习版最小：绝大多数本地/云模型走 OpenAI 兼容接口；原版有完整服务商管理（zhipu/qwen/...），M8.1 精读方向。

## ⚠️ 风险点

1. 表单 HTML 用字符串拼接 + escapeAttr 转义——若引入第三方 HTML 片段需审计注入面
2. 编辑保存后 `alert()` 错误且 `throw err` 保持模态打开——用户需先关弹窗再改，交互略粗糙（M8.1 可改表单内联错误）
3. 温度字段 `Number(input.value || 0.3)`——空输入兜底 0.3，非数字输入得 NaN（后端校验温度范围兜底）
4. 删除无二次确认的"输入名字"强化（学习版仅 showConfirm）

> 页脚：2026-10-17 · M8 模型设置页 · 对标 `EvoFlow/evopanel/src/pages/models.js`（学习版裁剪）
