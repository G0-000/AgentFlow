# evopanel/src/components/modal.js — modal.js（通用弹窗）

> **文件路径**: `evopanel/src/components/modal.js`
> **对标来源**: `EvoFlow/evopanel/src/components/modal.js`（630 行；裁剪：去掉 Tauri 拖拽与 browser-embed 联动，保留 showConfirm/showModal 两个核心导出）
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
showConfirm(message) → Promise<boolean>
  overlay + modal（取消/确认按钮）→ 点确认 true / 取消/遮罩/Esc false
showModal({title, html, actions}) → Promise<void>
  overlay + modal（标题/正文/actions 按钮 + 关闭）
  按钮 handler 可 await；不抛错则自动关闭（keepOpen 可保持）
```

## 📤 关键导出

- `showConfirm(message)` → `Promise<boolean>`
- `showModal({title, html, actions})` → `Promise<void>`

## 💡 设计思想

1. **替代原生 confirm()**：浏览器与（原版 Tauri）WebView 行为一致，且可样式化——对齐原版设计动机。
2. **Promise 化**：调用方 `await` 拿结果，UI 逻辑与弹窗解耦（models 页删除流程即 `showConfirm → remove → refresh`）。
3. **遮罩点击语义**：确认框 = 取消（false）；模态 = 关闭。ESC 均关闭。`settled` 标志保证只 resolve 一次（防重复点击/多事件竞争）。

## 🎯 实用场景

1. 模型删除确认：`const ok = await showConfirm('删除模型「x」？')` → 确认才调 DELETE。
2. 模型新增/编辑表单：`showModal({title, html: 表单, actions: [{label:'保存', handler}]})`。

## 🧩 顺序执行链

```text
showConfirm(message)
  ▼ 创建 overlay（escapeHtml 转义 message 后插入）
  ▼ 绑定：点遮罩→false / 确认→true / 取消→false / Esc→false
  ▼ 任一触发 → settled 检查 → _removeOverlay → resolve(v)
  （close 时移除 keydown 监听，防泄漏）
```

## ❓ Q&A / 知识点

**Q: `showModal` 的 handler 里 `throw err` 为什么不关弹窗？**
A: models 页保存失败时 `alert(err.message) + throw`——handler 抛错则 `_close()` 不执行（`await act.handler(overlay)` 抛异常，后续不跑），弹窗保持打开让用户修正重试。这是"表单校验失败保持弹窗"的惯用实现。

**Q: 为什么 modal 内容用 innerHTML 拼接 + escapeHtml？**
A: title/message/按钮 label 都是代码内字符串（可信任），但内容里可能带用户数据（模型名）——`escapeHtml` 统一转义防注入；`html` 正文（表单）由调用方自行保证安全（models 页对 value 用 escapeAttr）。

## ⚠️ 风险点

1. `escapeHtml` 与 `escapeAttr` 是两套转义（modal 内只有 escapeHtml，attr 转义在调用方）——勿混淆
2. `handler` 抛异常时 Promise 不 resolve、弹窗不关——若 handler 想"失败也关"需 `keepOpen:false` 显式处理（当前 models 页故意抛错保持打开）
3. 无 `aria-*` 无障碍属性（学习版最小；原版 630 行含焦点管理）

> 页脚：2026-10-17 · M8 通用弹窗 · 对标 `EvoFlow/evopanel/src/components/modal.js`（学习版裁剪）
