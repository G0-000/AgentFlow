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
- [🧩 代码解析](#🧩-代码解析)
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

## 🧩 代码解析

```js
import { modelsApi } from '../lib/api-client.js'
import { showConfirm, showModal } from '../components/modal.js'

export function renderModels(container) {
  container.innerHTML = `…工具栏(+新增) + 表格…`
  const tbody = container.querySelector('#models-tbody')

  async function refresh() {                    // ① 列表：GET /api/models
    const res = await modelsApi.list()
    tbody.innerHTML = ''
    for (const m of (res?.models) || []) {
      const tr = document.createElement('tr')
      tr.innerHTML = `…名称/服务商/模型/base_url/temp/状态(主模型badge)/操作…`
      tr.querySelector('[data-op="set-primary"]').addEventListener('click', async () => {
        await modelsApi.update(m.name, { is_primary: true }); refresh()   // ② 设默认
      })
      tr.querySelector('[data-op="edit"]').addEventListener('click', () => openForm(m))
      tr.querySelector('[data-op="del"]').addEventListener('click', async () => {
        const ok = await showConfirm(`删除模型「${m.name}」？不可恢复。`)   // ③ 删除确认
        if (!ok) return
        await modelsApi.remove(m.name); refresh()
      })
      tbody.appendChild(tr)
    }
  }

  function openForm(existing = null) {          // ④ 新增/编辑共用表单（showModal）
    const isEdit = !!existing
    const html = `…字段输入（编辑时 name disabled、api_key 打码）…`
    showModal({
      title: isEdit ? `编辑模型「${existing.name}」` : '新增模型',
      html,
      actions: [{ label: isEdit ? '保存' : '创建', primary: true, handler: async () => {
        const body = { provider, model, base_url, api_key, temperature, is_primary }
        if (isEdit) delete body.api_key          // PATCH 语义：留空则后端不改
        await (isEdit ? modelsApi.update(existing.name, body) : modelsApi.create(body))
        refresh()
      } }],
    })
  }
  container.querySelector('#add-model').addEventListener('click', () => openForm())
  refresh()
}
```

**逐块拆解**：

- **`refresh()`** — 列表渲染：每行绑定三个操作。**`set-primary`** 行内按钮 = `PATCH {is_primary:true}` → 后端事务翻转唯一主模型；**`edit`** 打开共用表单；**`del`** 先 `showConfirm` 再 `remove`。
- **`openForm(existing)`** — 新增/编辑一表单两用：`isEdit` 时 name 输入框 `disabled`（唯一标识不可改）、api_key 打码显示。**PATCH 语义关键**：编辑保存时 `delete body.api_key`——留空 = 不传该字段 = 后端不改 key（models.py 白名单收 None 才会更新）。
- **`handler` 保存逻辑** — 收集表单值 → 编辑走 `update(name, body)`（PATCH）、新增走 `create(body)`（POST）；成功 `refresh()`；失败 `alert + throw` 保持弹窗打开（modal.js 的 keepOpen 语义）。
- **`escapeHtml`/`escapeAttr`** — 表格单元格与表单 value 都转义；模型名等用户数据不直接进 innerHTML（防 XSS）。

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

> 页脚：2026-10-20 · M8 模型设置页 · 对标 `EvoFlow/evopanel/src/pages/models.js`（学习版裁剪；10-20 补 🧩 代码解析）
