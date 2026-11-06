// Incrusta el JS i el CSS de dist-demo/ a un sol HTML (dist-demo/hebra-demo.html),
// per obrir-lo amb doble clic o publicar-lo com una sola pàgina.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const dir = 'dist-demo';
let html = readFileSync(join(dir, 'index.html'), 'utf8');
html = html.replace(/<link rel="stylesheet"[^>]*href="\.\/([^"]+)"[^>]*>/g, (_, f) =>
  `<style>${readFileSync(join(dir, f), 'utf8')}</style>`);
html = html.replace(/<script type="module"[^>]*src="\.\/([^"]+)"[^>]*><\/script>/g, (_, f) =>
  `<script type="module">${readFileSync(join(dir, f), 'utf8').replace(/<\/script/g, '<\\/script')}</script>`);
html = html.replace(/<link rel="modulepreload"[^>]*>/g, '');
writeFileSync(join(dir, 'hebra-demo.html'), html);
console.log(`dist-demo/hebra-demo.html: ${(html.length / 1024).toFixed(0)} KB`);
