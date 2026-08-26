import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.VITE_DEV_API_TARGET ?? 'http://localhost:8080'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (proxyRequest) => proxyRequest.removeHeader('origin'))
        },
      },
    },
  },
})
