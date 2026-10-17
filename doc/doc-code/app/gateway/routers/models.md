# gateway/routers/models.py — models.py

> **文件路径**: `backend/app/gateway/routers/models.py`
> **目录位置**: gateway/routers → models.py
> **职责**: 模型管理 API（列表/创建/详情/PATCH/删除）

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
router(prefix="/api", tags=["models"])
  GET    /api/models          → list_all()
  POST   /api/models          → create()
  GET    /api/models/{name}   → get()
  PATCH  /api/models/{name}   → update() + 可选 is_primary
  DELETE /api/models/{name}   → delete()

存储: request.app.state.model_store (ModelStore, SQLite)
```

## 📤 关键导出

**router** — `models.router`

## 💡 设计思想

1. **裁剪对齐**：原版 models 路由 1000+ 行（探针/连接/降级），M7 只做配置 CRUD。
2. **PATCH 传 `is_primary:true` 即切换主模型**——runs 运行时现场读主模型，写 SQLite 后下一次 run 生效（验收点 4）。
3. **api_key 对外打码**：`ModelStore.to_dict(mask_key=True)`，不回显明文。

## 🎯 实用场景

1. 模型面板：增删改查模型连接
2. 切换对话模型：PATCH `{is_primary:true}`，下一次对话即用新模型（不重启）

## 🧩 顺序执行链

**创建模型链**：

```text
request: POST /api/models {name,model,api_key,...}
   ▼  create_model(request, body)
   ▼  store.create(...)                       ← 同名已存在 → ValueError → 409
   ▼  首个模型自动 is_primary=1
   ▼  return 201 to_dict(row)（api_key 打码）
```

**切换主模型链**：见 model_store.md 的顺序执行链（PATCH → set_primary → runs 现场读）。

## 🧩 代码解析（成块对照 models.py）

### 块 1：Pydantic 请求体——入参校验与默认值

```python
class ModelCreate(BaseModel):
    name: str = Field(..., description="模型唯一标识")
    provider: str = Field(default="openai-compatible")
    base_url: str = Field(default="")
    model: str = Field(default="", description="真实模型名")
    api_key: str = Field(default="")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    is_primary: bool = Field(default=False, description="是否设为主模型（首个模型自动主）")

class ModelPatch(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    is_primary: bool | None = None
```

**关键点**：

- **`Field(..., ...)` 的 `...` = 必填**：`name` 是创建时唯一必填；其余都有默认值（`provider` 默认 openai-compatible 让用户最少输入即可用）。
- **`ge=0.0, le=2.0`**：temperature 边界校验在**请求入口**（FastAPI 422 自动拒绝非法值），store 层不用再防御——校验前置。
- **`ModelPatch` 全部 Optional + `default=None`**：PATCH 语义是"只传想改的字段"。`model_dump(exclude_unset=True)` 只取出**客户端显式传过**的字段——`None` 与"没传"是两回事：`exclude_unset` 把没传的排除，传了 `null` 的会被留下（但白名单 + store 逻辑会处理）。

### 块 2：PATCH —— 字段更新与主模型切换解耦

```python
@router.patch("/models/{name}")
async def update_model(request: Request, name: str, body: ModelPatch) -> dict:
    store = _store(request)
    if store.get(name) is None:
        raise HTTPException(status_code=404, detail=f"模型不存在: {name}")

    fields = body.model_dump(exclude_unset=True, exclude={"is_primary"})
    try:
        row = store.update(name, **fields)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if body.is_primary is not None and body.is_primary:
        store.set_primary(name)
        row = store.get(name)
    return store.to_dict(row)
```

**关键点**：

- **先 404 预检再操作**：`store.get(name)` 先确认存在，避免 `store.update` 抛 ValueError 再转 404（也转了，但预检让错误路径更早、更明确）。
- **`exclude={"is_primary"}`**：is_primary 不进 `store.update` 的字段白名单（model_store 白名单没有它）——单独走 `set_primary`。两步解耦：字段更新（update）与状态翻转（set_primary）互不干扰。
- **`exclude_unset=True`**：客户端 PATCH `{temperature: 0.7}` 时，`fields = {"temperature": 0.7}`；没传的字段不进 SQL。这是"局部更新"的实现关键。
- **`store.update` 返回 `sqlite3.Row`**，`to_dict` 打码后返回——api_key 不回显明文。

### 块 3：错误映射——ValueError → HTTP 状态码

```python
@router.post("/models", status_code=201)
async def create_model(request: Request, body: ModelCreate) -> dict:
    try:
        row = store.create(...)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return store.to_dict(row)
```

**关键点**：

- **`ValueError → 409`（创建同名）**、**`ValueError → 404`（更新/删除不存在）**：store 层只抛领域异常（`ValueError("模型已存在")`），路由层负责映射成 HTTP 语义。**领域层不知道 HTTP**——职责分离。
- `raise ... from e`：保留异常链（FastAPI 日志里能看到原始 ValueError），前端拿到的是 `detail` 文本。

## ❓ Q&A / 知识点

**Q: 重复创建同名模型返回什么？**
A: 409 Conflict（`store.create` 抛 `ValueError("模型已存在: name")` → 路由转 409）；更新/删除不存在返回 404。

**Q: 为什么 PATCH 切换主模型不直接用 `store.update(name, is_primary=True)`？**
A: 两个原因：① `ModelStore.update` 的字段白名单**故意不含 `is_primary`**（它是状态翻转不是字段更新——语义上"设主 = 其他全部降级"，两步 SQL）；② 若混进字段更新，调用方可能"只更新了 is_primary 而忘了清其他行"，产生多个主模型。所以路由层显式两步：`update(name, **fields)` → `set_primary(name)`。

**Q: PATCH 传 `temperature: null` 会发生什么？**
A: `model_dump(exclude_unset=True)` 会把显式传的 `null` 保留（`exclude_unset` 只排除"没传"，不排除"传了 None"）→ `store.update(name, temperature=None)` → 白名单放行 → SQL 写入 `NULL`。这是 PATCH 的边界语义：传 null = 置空。若想禁止，需在 ModelPatch 里用 `exclude_none=True` 或校验器——M7 未做限制（温度 NULL 会被 `to_chat_config` 传给工厂，模型默认值兜底）。

**Q: 为什么错误用 `from e` 链式抛出？**
A: FastAPI 的异常日志会保留完整链——`HTTPException` 是"面向客户端"的壳，原始 `ValueError` 是"面向开发者"的根。`raise ... from e` 让开发者在服务日志里直接看到领域层原因（哪一行、什么冲突），而不是只有 HTTP 壳。

## ⚠️ 风险点

1. `/api/models/{name}` 是动态段，勿在其前再定义 `/api/models/xxx` 静态段（FastAPI 按定义顺序匹配）
2. PATCH 先改字段再独立处理 `is_primary`（两步解耦，勿合并）
3. 传 `temperature: null` 会写入 NULL——若不想接受需在 ModelPatch 加校验
4. api_key 经 `to_dict` 打码返回，但 POST 响应也走 `to_dict`——客户端创建后拿到的也是打码值（无法回读明文，属预期）

> 页脚：2026-10-13 · M7 Gateway 核心 · 对齐 `evoflow/gateway/routers/models.py`（裁剪）
