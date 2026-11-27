// Comprobación SEO tras el build: títulos únicos y ≤ 60, descripciones ≤ 155, un H1, imágenes con ALT,
// enlaces internos sin parámetros, JSON-LD válido. Uso: node tools/seo-check.mjs (después de npm run build).
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
const files = [];
const walk = (d) => readdirSync(d).forEach((f) => { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : f.endsWith('.html') && files.push(p); });
walk('dist');
const titles = new Map(); let errors = 0;
const err = (f, m) => { errors++; console.log(`✗ ${f}: ${m}`); };
const dec = (s) => s.replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"');
for (const f of files) {
  const h = readFileSync(f, 'utf8');
  const noindex = /<meta name="robots" content="noindex/.test(h);
  const title = dec(h.match(/<title>([^<]*)<\/title>/)?.[1] ?? '');
  const desc = dec(h.match(/<meta name="description" content="([^"]*)"/)?.[1] ?? '');
  if (!noindex) { if (titles.has(title)) err(f, `título repetido con ${titles.get(title)}`); titles.set(title, f); }
  if (title.length > 60) err(f, `título largo (${title.length})`);
  if (!desc || desc.length > 155) err(f, `descripción de ${desc.length} caracteres`);
  const h1 = (h.match(/<h1[\s>]/g) || []).length;
  if (!noindex && h1 !== 1 && !f.includes('/p/demo')) err(f, `${h1} H1`);
  for (const img of h.match(/<img[^>]*>/g) || []) if (!/alt="[^"]+"/.test(img)) err(f, `imagen sin ALT: ${img.slice(0, 80)}`);
  for (const [, href] of h.matchAll(/<a [^>]*href="(\/[^"]*)"/g)) if (href.includes('?')) err(f, `enlace con parámetros: ${href}`);
  for (const [, j] of h.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) { try { JSON.parse(j); } catch { err(f, 'JSON-LD no válido'); } }
  if (/class="pend"|\[(RAZÓN SOCIAL|RAÓ SOCIAL|COMPANY NAME|NIF|fecha de publicación|data de publicació|publication date)/.test(h)) err(f, "texto pendiente visible (claudàtors): omplir src/legal.ts");
}
console.log(errors ? `\n${errors} problemas en ${files.length} páginas` : `✓ ${files.length} páginas sin problemas SEO`);
process.exit(errors ? 1 : 0);
