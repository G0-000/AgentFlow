# ============================================================================
# AgentFlow · gateway/sse.py —— SSE 流式输出（裁剪版）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/app/gateway/sse.py
# 对标来源: evoflow/gateway/openai_stream_normalize.py / sse_ui_normalize.py
#   原版做"OpenAI chunk → 前端 UI 事件"的归一化 + 大字段裁剪（sse_slim）。
#   M7 裁剪：只做"回复文本逐块推送"这一件事，用 sse-starlette。
# 里程碑: M7（Gateway 核心）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────┐
# │ delta_event(text) → {"event":"delta","data": json}     │
# │ done_event()     → {"event":"done","data": {...}}      │
# │ error_event(msg) → {"event":"error","data": {...}}     │
# │                                                         │
# │ EventSourceResponse(content_generator)  ← sse-starlette │
# │   逐块 yield dict，框架自动按 SSE 帧编码                  │
# └────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 原版 SSE 归一化复杂（messages/values/end 多事件、裁剪去重）；
#    M7 只暴露给前端一种语义：delta（文本块）/ done（结束）/ error（失败）。
# 2. 事件名固定（delta/done/error），前端按 event 分支即可，不再解析 OpenAI chunk。
# 3. 用 sse-starlette 的 EventSourceResponse，帧编码（data:/心跳）交给它。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. delta_event / done_event / error_event: 构造标准 SSE 事件 dict
# 2. EventSourceResponse: 直接 re-export（路由层 from ... import EventSourceResponse）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. data 必须是 JSON 字符串（EventSourceResponse 要求 str 或可用 json 序列化的 dict？
#    实测：传 dict 时 sse-starlette 会再 json.dumps；这里统一手动 dumps 成 str 最稳）
# 2. 客户端断开（SSE 取消）会在生成器抛异常，路由层需 try/finally 落库 run 状态
# ============================================================================

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from sse_starlette import EventSourceResponse


def delta_event(text: str) -> dict:
    """一块回复文本：event=delta, data={"delta": text}。"""
    return {"event": "delta", "data": json.dumps({"delta": text}, ensure_ascii=False)}


def done_event(full_text: str) -> dict:
    """流结束：event=done, data={"status":"success","response": full_text}。"""
    return {
        "event": "done",
        "data": json.dumps(
            {"status": "success", "response": full_text}, ensure_ascii=False
        ),
    }


def error_event(message: str) -> dict:
    """流失败：event=error, data={"error": message}。"""
    return {
        "event": "error",
        "data": json.dumps({"error": message}, ensure_ascii=False),
    }


async def sse_text_stream(chunks: AsyncIterator[str]) -> AsyncIterator[dict]:
    """把一个"逐块产文本"的异步生成器包成 SSE 事件流（delta... → done）。

    路由层用法:
        return EventSourceResponse(sse_text_stream(my_async_gen))
    """
    full = ""
    async for text in chunks:
        if text:
            full += text
            yield delta_event(text)
    yield done_event(full)


__all__ = [
    "EventSourceResponse",
    "delta_event",
    "done_event",
    "error_event",
    "sse_text_stream",
]
