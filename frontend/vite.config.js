import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy all backend API routes to FastAPI on port 8000
      '/ingest-pdf':    'http://localhost:8000',
      '/chat':          'http://localhost:8000',
      '/crawl':         'http://localhost:8000',
      '/sessions':      'http://localhost:8000',
      '/memory':        'http://localhost:8000',
      '/analytics':     'http://localhost:8000',
      '/mcp':           'http://localhost:8000',
      '/health':        'http://localhost:8000',
      // Legacy endpoint (kept for backward compat)
      '/analyze-pdf':   'http://localhost:8000',
    }
  }
})
