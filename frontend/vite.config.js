import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/works': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/stats': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/sync': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      }
    }
  }
})
