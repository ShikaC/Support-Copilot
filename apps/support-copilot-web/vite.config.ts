import { defineConfig } from 'vitest/config'
import type { ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.VITE_DEV_API_TARGET ?? 'http://localhost:8080'
const apiProxy: Readonly<Record<string, ProxyOptions>> = {
  '/api': {
    target: apiTarget,
    changeOrigin: true,
    configure(proxy) {
      proxy.on('proxyReq', (proxyRequest) => proxyRequest.removeHeader('origin'))
    },
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: apiProxy,
  },
  preview: {
    proxy: apiProxy,
  },
  test: {
    // Serialize rendered files that share process-global JSDOM shims while keeping a bounded timeout.
    fileParallelism: false,
    testTimeout: 10_000,
  },
})
