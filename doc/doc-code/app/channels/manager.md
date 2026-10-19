# channels/manager.py — manager.py

> **文件路径**: `backend/app/channels/manager.py`
> **目录位置**: app/channels → manager.py
> **职责**: 渠道注册表 + 入站路由——ChannelManager（register/unregister/get/route_inbound/start_all/stop_all），对齐原版 manager 位置的**最小核心**

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
ChannelManager（对齐原版 manager.py 位置；原版 2712 行只留核心约 130 行）
  register(name, channel)      注册渠道实例（同名覆盖告警）
  unregister(name)             注销
  get(name) → Channel|None     取渠道
  registered() → list[str]     已注册渠道名
  route_inbound(msg) → bool    按 msg.channel_name 路由到渠道.on_message
  start_all() / stop_all()     批量启停（多渠道统一装配入口）
  build({name: channel})       一行批量装载
```

## 📤 关键导出

**ChannelManager**（经 `app.channels` 再导出）

## 💡 设计思想

1. **对齐原版位置（2026-10-18 补位）**：渠道注册表 + 入站路由由 manager 承担——原版 2712 行（IM 快捷命令/会话索引/transcript/诊断），AgentFlow 只留「注册 + 入站路由」最小核心（纠偏 4 原最小 scope）。
2. **多渠道统一装配**：`serve_all → ChannelManager.start_all` 一行启动全部渠道——接第 2 个平台时 `build({"feishu": ..., "wecom": ...})` 注册即可，不再各自启动。
3. **入站路由容错**：未注册渠道 / 无 on_message 的渠道 → 仅告警返回 False，不抛出——单渠道误发不炸整进程。
4. **不持有 MessageBus**：总线由装配层传入渠道，manager 只做注册与路由，保持最小耦合。

## 🎯 实用场景

1. 多渠道启动：`ChannelManager.build({...}).start_all()` 统一装配飞书 + 企微
2. 入站分发：dispatcher 消费到 InboundMessage 后 `manager.route_inbound(msg)` 按渠道名路由
3. 运行期管理：`unregister` 下线渠道 / `registered()` 盘点在线渠道

## 🧩 顺序执行链

**装配链（多渠道）**：

```text
装配层构造各渠道实例（FeishuChannel/WecomChannel…）
   ▼  mgr = ChannelManager.build({"feishu": ch1, "wecom": ch2})
   ▼  mgr.start_all()                    ← 逐渠道 start()（单个失败只记日志）
   ▼  （持续运行）入站事件到达
```

**入站路由链**：

```text
InboundMessage 到达（channel_name="wecom"）
   ▼  mgr.route_inbound(msg)
   ▼  get(msg.channel_name)              ← 注册表查找
   ▼  命中 → channel.on_message(msg)     ← 同步分发（对齐 M7 渠道回调形态）
   ▼  未命中 → 告警 + return False       ← 不抛出
```

## 🧩 代码解析

### 注册与路由

```python
class ChannelManager:
    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}

    def register(self, name: str, channel: Channel) -> None:
        if name in self._channels:
            logger.warning("[Manager] channel %r re-registered (overwrite)", name)
        self._channels[name] = channel

    def route_inbound(self, msg: InboundMessage) -> bool:
        channel = self._channels.get(msg.channel_name)
        if channel is None:
            logger.warning("[Manager] no channel registered for %r", msg.channel_name)
            return False
        on_message = getattr(channel, "on_message", None)
        if on_message is None:
            logger.warning("[Manager] channel %r has no on_message handler", msg.channel_name)
            return False
        on_message(msg)
        return True
```

**关键点**：

- **`route_inbound` 按 `msg.channel_name` 查注册表**——路由键是消息自带的渠道名，不是调用方传入的，天然支持多渠道路由。
- **`getattr(channel, "on_message", None)`**：Channel ABC 只约束 start/stop，on_message 是渠道约定俗成的方法——用 getattr 防御渠道没实现它的情况。
- **同名重复注册 = 覆盖 + 告警**：不抛异常（装配重启场景可幂等重注册），但记录告警便于排查。
- **`build` 静态工厂**：装配层一行 `ChannelManager.build({...})` 生成注册表，与 `start_all` 配套构成「注册 → 启动」两段式。

## ❓ Q&A

**Q: ChannelManager 现在被谁调用？**
A: 目前**无调用方**（feishu serve 仍独立启动单渠道）。与 MessageBus 一样是「架构位置先行」：M8.1 多渠道实装时作为统一装配入口接入。

**Q: 为什么不直接持有 MessageBus？**
A: 最小耦合——manager 只做注册 + 路由；总线、dispatcher、渠道之间的协作由装配层编排。原版 manager 与 bus 是 async 协奏，AgentFlow 单渠道同步阶段没必要提前绑死。

**Q: start_all 里单个渠道 start 失败会怎样？**
A: 记异常日志后继续启动其他渠道（try/except 包住每个渠道）——一个渠道坏了不影响整体上线。

**Q: route_inbound 为什么不抛异常？**
A: 入站路由是"尽力分发"语义：未注册渠道（如测试误发）告警返回 False，调用方可决定忽略或重试；抛异常会让 dispatcher 消费循环崩掉。

## ⚠️ 风险点

1. **无调用方**：当前是备用架构件，别误以为多渠道已生效
2. `route_inbound` 是**同步分发**（对齐 M7 渠道 on_message 同步回调）；原版 manager/bus 是 async 协奏——M8.1 多渠道实装时需异步化改造
3. 同名注册覆盖：装配时渠道名必须唯一（重复名 = 后者覆盖前者 + 告警）
4. 渠道 start 阻塞型实现（如 WS 长连接）会让 start_all 卡在第一个渠道——生产用 start 起后台线程（feishu serve 已如此）

> 页脚：2026-10-18 · M7 架构对齐补位 · 对齐 `evoflow/app/channels/manager.py`（最小核心）
