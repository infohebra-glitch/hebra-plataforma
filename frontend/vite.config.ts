import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// El backend serveix dist/ a /app amb «SPA fallback».
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: false } },
  },
  preview: { port: 4173 },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
} as import('vite').UserConfig & { test: unknown });
