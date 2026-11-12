import { defineConfig } from 'astro/config';

// Cambiar `site` cuando tengamos el dominio definitivo.
export default defineConfig({
  site: 'https://hebra.example',
  build: { format: 'directory' },
  trailingSlash: 'ignore',
});
