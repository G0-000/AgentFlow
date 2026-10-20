// ============================================================================
// AgentFlow · evopanel/tests/test_api_client.js —— API 封装单测（vitest）
// ============================================================================
// 里程碑: M8（前端界面）—— 验收清单"测试需求"：API 封装请求/错误处理
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. node 环境 + 手动 mock global fetch：测 apiUrl 路径归一、request 的
//    JSON 序列化/错误归一（非 2xx → 抛 detail）、token 头注入。
// 2. streamSSE 用 ReadableStream 模拟后端 SSE 帧（delta/done/error），
//    验证逐块回调与解析逻辑——这是聊天页流式显示的核心契约。
// ============================================================================

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiUrl, request, streamSSE, setToken, getToken, clearToken } from '../src/lib/api-client.js'

// node 环境无 localStorage：提供最小内存实现（api-client.js 直接引用全局）
globalThis.localStorage = (() => {
  let store = {}
  return {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v) },
    removeItem: (k) => { delete store[k] },
    clear: () => { store = {} },
  }
})()

describe('apiUrl', () => {
  it('补全前导斜杠', () => {
    expect(apiUrl('models')).toContain('/api/models')
  })
  it('已是斜杠开头不重复', () => {
    expect(apiUrl('/models')).toContain('/api/models')
  })
})

describe('request', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    clearToken()
  })

  it('GET 不带 body，成功返回 JSON', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ models: [] }) })
    const res = await request('/models')
    expect(res).toEqual({ models: [] })
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/models'),
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('POST 序列化 JSON body', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ run_id: 'r1' }) })
    await request('/runs', { method: 'POST', body: { message: 'hi', thread_id: null } })
    const [, opts] = fetch.mock.calls[0]
    expect(opts.body).toBe('{"message":"hi","thread_id":null}')
  })

  it('非 2xx 抛 detail 错误（后端统一错误格式）', async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: '用户名或密码错误' }),
    })
    await expect(request('/auth/login', { method: 'POST', body: {} })).rejects.toThrow(
      '用户名或密码错误',
    )
  })

  it('非 JSON 错误响应退化为 HTTP 状态', async () => {
    fetch.mockResolvedValue({ ok: false, status: 503, json: async () => { throw new Error('no json') } })
    await expect(request('/x')).rejects.toThrow('HTTP 503')
  })

  it('有 token 时注入 Authorization 头', async () => {
    setToken('abc')
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) })
    await request('/models')
    const [, opts] = fetch.mock.calls[0]
    expect(opts.headers.Authorization).toBe('Bearer abc')
    clearToken()
  })
})

describe('streamSSE', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    clearToken()
  })

  /** 构造后端 SSE 响应。frameSep 默认 \r\n\r\n（sse-starlette 生产真实格式）；
   *  \n\n 是标准 SSE 分隔，用于兼容性用例。 */
  function sseResponse(frames, frameSep = '\r\n\r\n') {
    const text = frames.map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}${frameSep}`).join('')
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(text))
        controller.close()
      },
    })
    return { ok: true, status: 200, body: stream }
  }

  it('POST /runs 创建后消费 delta/done 并聚合全文', async () => {
    fetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ run_id: 'r1', thread_id: 't1' }) })
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'delta', data: { delta: '你' } },
          { event: 'delta', data: { delta: '好' } },
          { event: 'done', data: { status: 'success', response: '你好' } },
        ]),
      )
    const deltas = []
    const done = []
    const created = []
    await streamSSE({
      message: 'hi',
      onCreated: (run) => created.push(run),
      onDelta: (d) => deltas.push(d),
      onDone: (full) => done.push(full),
    })
    expect(created[0].thread_id).toBe('t1')
    expect(deltas).toEqual(['你', '好'])
    expect(done).toEqual(['你好'])
  })

  it('标准 \n\n 帧分隔兼容（非 sse-starlette 实现）', async () => {
    fetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ run_id: 'r4', thread_id: 't4' }) })
      .mockResolvedValueOnce(
        sseResponse([{ event: 'delta', data: { delta: 'hi' } }, { event: 'done', data: { status: 'success', response: 'hi' } }], '\n\n'),
      )
    const deltas = []
    const done = []
    await streamSSE({ message: 'x', onDelta: (d) => deltas.push(d), onDone: (f) => done.push(f) })
    expect(deltas).toEqual(['hi'])
    expect(done).toEqual(['hi'])
  })

  it('error 事件触发 onError', async () => {
    fetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ run_id: 'r2', thread_id: 't2' }) })
      .mockResolvedValueOnce(sseResponse([{ event: 'error', data: { error: '模型超时' } }]))
    const errors = []
    await streamSSE({ message: 'x', onError: (e) => errors.push(e) })
    expect(errors).toEqual(['模型超时'])
  })

  it('流打开失败（非 200）触发 onError', async () => {
    fetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ run_id: 'r3' }) })
      .mockResolvedValueOnce({ ok: false, status: 404 })
    const errors = []
    await streamSSE({ message: 'x', onError: (e) => errors.push(e) })
    expect(errors[0]).toContain('404')
  })
})
