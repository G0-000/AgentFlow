// ============================================================================
// AgentFlow · evopanel/vite.config.js —— 开发服务器 + /api 代理
// ============================================================================
// 对标来源: EvoFlow/evopanel/vite.config.js（裁剪：原版含 tailwind/zcode vendored
//   树/若干自定义 plugin；学习版只留 react plugin + 一个 /api 代理）
// 里程碑: M8（前端界面）
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. 前端永远写相对路径 `/api/*`，由 Vite dev server 代理转发到 gateway——
//    页面代码不写死 gateway 地址（对齐原版 api-client.js 的 apiUrl 逻辑）。
// 2. 生产构建（vite build）产物是纯静态文件，/api 前缀交给反代或 gateway
//    同源部署处理；学习版以 dev 模式为主。
// 3. 端口 38012 对齐原版 gateway 默认端口（EvoFlow backend/app_server）。
// ============================================================================

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const GATEWAY_PORT = process.env.GATEWAY_PORT || '38012'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 所有 /api 请求转发到 gateway（FastAPI），WebSocket/SSE 由 proxy 透传
      '/api': {
        target: `http://127.0.0.1:${GATEWAY_PORT}`,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.js'],
  },
})
