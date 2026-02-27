import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // /chat uses SSE streaming.
      // Do NOT call proxyRes.pipe(res) here — Vite already pipes the response internally.
      // Calling pipe() a second time sends every chunk twice, causing duplicate text.
      // Just set headers to disable proxy buffering so SSE tokens flow in real-time.
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no';
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
      // /ingest-pdf also uses SSE streaming for real-time progress
      '/ingest-pdf': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no';
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
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
