import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // /chat uses SSE streaming — disable proxy buffering so tokens flow in real-time
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Disable response buffering for SSE
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // Tell Node's http-proxy to flush chunks immediately (SSE support)
            proxyRes.pipe(res, { end: true });
          });
        },
      },
      // All other backend API routes
      '/ingest-pdf':  { target: 'http://localhost:8000', changeOrigin: true },
      '/crawl':       { target: 'http://localhost:8000', changeOrigin: true },
      '/sessions':    { target: 'http://localhost:8000', changeOrigin: true },
      '/memory':      { target: 'http://localhost:8000', changeOrigin: true },
      '/analytics':   { target: 'http://localhost:8000', changeOrigin: true },
      '/mcp':         { target: 'http://localhost:8000', changeOrigin: true },
      '/health':      { target: 'http://localhost:8000', changeOrigin: true },
      '/analyze-pdf': { target: 'http://localhost:8000', changeOrigin: true },
    }
  }
})
