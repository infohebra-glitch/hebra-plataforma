// Feed RSS del blog por idioma: ayuda a que buscadores y lectores descubran cada artículo nuevo.
import { getCollection } from 'astro:content';
import { path, type Lang } from './i18n';

const SITE = 'https://hebraia.com';
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const NAME = { es: 'Blog de Hebra', ca: 'Blog d’Hebra', en: 'Hebra blog' };
const DESC = {
  es: 'Lo que pasa dentro del probador, el origen de la ropa y las normas que llegan a la moda.',
  ca: 'El que passa dins l’emprovador, l’origen de la roba i les normes que arriben a la moda.',
  en: 'What happens inside the fitting room, where clothes come from and the rules coming to fashion.',
};

export async function feed(lang: Lang) {
  const posts = (await getCollection('blog', (e) => e.id.startsWith(`${lang}/`))).sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
  const items = posts.map((p) => {
    const url = SITE + path(lang, `/blog/${p.id.split('/').slice(1).join('/')}/`);
    return `<item><title>${esc(p.data.title)}</title><link>${url}</link><guid isPermaLink="true">${url}</guid><pubDate>${p.data.date.toUTCString()}</pubDate><category>${esc(p.data.kicker)}</category><description>${esc(p.data.description)}</description></item>`;
  }).join('');
  const self = SITE + path(lang, '/blog/rss.xml');
  const xml = `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>${esc(NAME[lang])}</title><link>${SITE + path(lang, '/blog/')}</link><description>${esc(DESC[lang])}</description><language>${lang}</language><atom:link href="${self}" rel="self" type="application/rss+xml"/>${items}</channel></rss>`;
  return new Response(xml, { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
}
