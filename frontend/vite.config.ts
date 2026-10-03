import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  // In Docker the API is not on localhost: compose sets API_PROXY_TARGET=http://api:8000 for the web container.
  const target = process.env.API_PROXY_TARGET || new URL(env.VITE_API_URL ?? '/api/v1', 'http://127.0.0.1:8000').origin
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: { '/api': { target, changeOrigin: true } },
    },
  }
})
