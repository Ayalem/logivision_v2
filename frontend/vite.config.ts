import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// FastAPI runs on :8000 (services/api/main.py). During `vite dev` we proxy
// /api and /ws so the frontend talks to the real backend without CORS.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api':    { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':     { target: 'ws://localhost:8000',   ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200, // R3F bundles are chunky
  },
})
