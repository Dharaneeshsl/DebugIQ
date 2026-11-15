import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('recharts')) return 'charts';
          if (id.includes('react-force-graph') || id.includes('force-graph')) return 'graph';
          if (id.includes('axios')) return 'http';
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: path => path.replace(/^\/api/, '') } }
  },
  preview: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: path => path.replace(/^\/api/, '') } }
  },
})
