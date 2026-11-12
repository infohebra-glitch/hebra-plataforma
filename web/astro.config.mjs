import { defineConfig } from 'astro/config';

// Dominio definitivo (12-11-2026).
export default defineConfig({
  site: 'https://hebraia.com',
  build: { format: 'directory' },
  trailingSlash: 'ignore',
});
