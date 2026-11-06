import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// El backend serveix dist/ a /app amb «SPA fallback».
// Amb --mode demo (npm run build:demo; .env.demo posa VITE_DEMO=1) es fa la demo d'un sol fitxer: dades falses,
// rutes amb # i camins relatius, tot en un paquet (scripts/demo-un-fitxer.mjs l'incrusta a l'HTML).
export default defineConfig(({ mode }) => {
  const demo = mode === 'demo';
  return {
  base: demo ? './' : '/app/',
  plugins: [react()],
  build: demo
    ? { outDir: 'dist-demo', emptyOutDir: true, assetsInlineLimit: 100000, rollupOptions: { output: { inlineDynamicImports: true } } }
    : { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: false } },
  },
  preview: { port: 4173 },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
  } as import('vite').UserConfig & { test: unknown };
});
