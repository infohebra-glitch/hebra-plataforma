// Sitemap con las tres versiones de cada página enlazadas entre sí (hreflang).
// Sólo incluye páginas indexables: las de src/seo.ts sin noindex y los artículos del blog.
import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { langs, path } from '../i18n';
import { sitemapRoutes } from '../seo';

export const GET: APIRoute = async ({ site }) => {
  const posts = await getCollection('blog');
  const lastmod = new Map<string, string>();
  for (const p of posts) {
    const slug = p.id.split('/').slice(1).join('/');
    const d = p.data.date.toISOString().slice(0, 10);
    const r = `/blog/${slug}/`;
    if (!lastmod.has(r) || lastmod.get(r)! < d) lastmod.set(r, d);
  }
  const routes = [...sitemapRoutes, ...lastmod.keys()];
  const url = (l: (typeof langs)[number], r: string) => new URL(path(l, r), site).href;
  const body = routes.flatMap((r) => langs.map((l) => `  <url>
    <loc>${url(l, r)}</loc>${lastmod.has(r) ? `\n    <lastmod>${lastmod.get(r)}</lastmod>` : ''}
${langs.map((a) => `    <xhtml:link rel="alternate" hreflang="${a}" href="${url(a, r)}"/>`).join('\n')}
    <xhtml:link rel="alternate" hreflang="x-default" href="${url('es', r)}"/>
  </url>`)).join('\n');
  return new Response(`<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${body}
</urlset>
`, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
