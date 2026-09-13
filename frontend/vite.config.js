import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  preview: {
    host: '0.0.0.0',
    allowedHosts: [
      'genuine-expression-production-66e8.up.railway.app',
      '.up.railway.app'
    ]
  }
})