import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, type ProxyOptions } from 'vite'

// The plate service; Compose publishes it on host port 8100. The browser always calls
// `/api/...`, which this proxy (and nginx in the container) forwards to the service.
const api = process.env.DASHBOARD_API ?? 'http://127.0.0.1:8100'
const port = Number(process.env.DASHBOARD_PORT ?? 5174)

const proxy: Record<string, ProxyOptions> = {
  '/api': {
    target: api,
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@fonts': fileURLToPath(new URL('../../plate_reader/synthetic/fonts', import.meta.url)),
      // Tests and stories read the committed results; the app fetches them from the service.
      '@results': fileURLToPath(new URL('../../results', import.meta.url)),
    },
  },
  server: {
    port,
    strictPort: true,
    proxy,
    // The plate fonts live with the synthetic generator, two levels up.
    fs: { allow: ['.', '../../plate_reader/synthetic/fonts', '../../results'] },
  },
  preview: { port, strictPort: true, proxy },
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 1200,
  },
  // ONNX Runtime Web loads its WebAssembly from /ort at run time; pre-bundling it breaks that.
  optimizeDeps: { exclude: ['onnxruntime-web'] },
})
