import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/euro-office-server': {
        target: 'http://10.18.113.9',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/euro-office-server/, ''),
      },
    },
  },
})
