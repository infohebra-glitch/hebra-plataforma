// SEO de cada página: título completo (único, ≤ 60 caracteres) y meta descripción (≤ 155 caracteres).
// Base.astro usa estos valores si la ruta está aquí; si no, usa los que le pasa la vista.
// `npm run build` comprueba las longitudes con tools/seo-check.mjs.
import type { Lang } from './i18n';

type Entry = { title: string; desc?: string; noindex?: boolean };

export const seo: Record<Lang, Record<string, Entry>> = {
  es: {
    '/': { title: 'Hebra · Lo que pasa dentro del probador', desc: 'Hebra mide lo que pasa en el probador de tu tienda de moda: qué ropa se prueba y no se vende, y por qué. Una etiqueta inteligente en cada prenda.' },
    '/probador/': { title: 'Probador: pruebas, tallas y motivos de no compra · Hebra', desc: 'Qué prendas entran en cada cabina, cuáles se venden y por qué no se llevan las demás. Avisos en tienda, informe semanal y pruebas con grupo de control.' },
    '/origen/': { title: 'Origen: trazabilidad de la cadena de cada prenda · Hebra', desc: 'La cadena de cada modelo en cuatro etapas, certificados con aviso de caducidad y coste ambiental con Ecobalyse. Para marcas de moda de 1 a 5 tiendas.' },
    '/ficha/': { title: 'La ficha: la historia de la prenda en el móvil · Hebra', desc: 'Al tocar la prenda con el móvil se abre su ficha: composición, cuidado y origen para tu cliente, y lo que pasa en el probador para ti. Sin app.' },
    '/como-funciona/': { title: 'Cómo funciona la etiqueta inteligente de Hebra', desc: 'Una etiqueta en cada prenda, una tienda que la reconoce sola y una acción cada lunes. Prueba el simulador del probador.' },
    '/blog/': { title: 'Blog de Hebra: probadores, tallas y origen en moda', desc: 'Lo que aprendemos sobre probadores, tallas, origen y tiendas de moda.' },
    '/nosotros/': { title: 'Nosotros: misión, visión y valores · Hebra', desc: 'Hebra nace en Barcelona para que las marcas de moda con tienda propia sepan qué pasa en su probador y de dónde viene lo que venden.' },
    '/contacto/': { title: 'Contacto: pide una demo de Hebra', desc: 'Escríbenos y en media hora te enseñamos la etiqueta, la ficha y los datos del probador con prendas reales. Respondemos desde clientes@hebraia.com.' },
    '/piloto/': { title: 'Piloto de 8 semanas en tu tienda de moda · Hebra', desc: 'Ocho semanas en una tienda para demostrar el valor de Hebra con datos: criterios de éxito por escrito, informe cada lunes y grupo de control.' },
    '/privacidad/': { title: 'Política de privacidad · Hebra' },
    '/aviso-legal/': { title: 'Aviso legal · Hebra' },
    '/cookies/': { title: 'Política de cookies · Hebra' },
    '/privacidad-ficha/': { title: 'Privacidad de la ficha de la prenda · Hebra' },
    '/gracias/': { title: 'Mensaje enviado · Hebra', noindex: true },
    '/p/demo/': { title: 'Ficha de ejemplo · Hebra', noindex: true },
  },
  ca: {
    '/': { title: 'Hebra · El que passa dins l’emprovador', desc: 'Hebra mesura el que passa a l’emprovador de la teva botiga de moda: quina roba s’emprova i no es ven, i per què. Una etiqueta intel·ligent a cada peça.' },
    '/probador/': { title: 'Emprovador: proves, talles i motius de no compra · Hebra', desc: 'Quines peces entren a cada cabina, quines es venen i per què no s’enduen les altres. Avisos a botiga, informe setmanal i proves amb grup de control.' },
    '/origen/': { title: 'Origen: traçabilitat de la cadena de cada peça · Hebra', desc: 'La cadena de cada model en quatre etapes, certificats amb avís de caducitat i cost ambiental amb Ecobalyse. Per a marques de moda d’1 a 5 botigues.' },
    '/ficha/': { title: 'La fitxa: la història de la peça al mòbil · Hebra', desc: 'En tocar la peça amb el mòbil s’obre la seva fitxa: composició, cura i origen per al teu client, i el que passa a l’emprovador per a tu. Sense app.' },
    '/como-funciona/': { title: 'Com funciona l’etiqueta intel·ligent d’Hebra', desc: 'Una etiqueta a cada peça, una botiga que la reconeix sola i una acció cada dilluns. Prova el simulador de l’emprovador.' },
    '/blog/': { title: 'Blog d’Hebra: emprovadors, talles i origen a la moda', desc: 'El que aprenem sobre emprovadors, talles, origen i botigues de moda.' },
    '/nosotros/': { title: 'Nosaltres: missió, visió i valors · Hebra', desc: 'Hebra neix a Barcelona perquè les marques de moda amb botiga pròpia sàpiguen què passa al seu emprovador i d’on ve el que venen.' },
    '/contacto/': { title: 'Contacte: demana una demo d’Hebra', desc: 'Escriu-nos i en mitja hora t’ensenyem l’etiqueta, la fitxa i les dades de l’emprovador amb peces reals. Responem des de clientes@hebraia.com.' },
    '/piloto/': { title: 'Pilot de 8 setmanes a la teva botiga de moda · Hebra', desc: 'Vuit setmanes en una botiga per demostrar el valor d’Hebra amb dades: criteris d’èxit per escrit, informe cada dilluns i grup de control.' },
    '/privacidad/': { title: 'Política de privacitat · Hebra' },
    '/aviso-legal/': { title: 'Avís legal · Hebra' },
    '/cookies/': { title: 'Política de galetes · Hebra' },
    '/privacidad-ficha/': { title: 'Privacitat de la fitxa de la peça · Hebra' },
    '/gracias/': { title: 'Missatge enviat · Hebra', noindex: true },
    '/p/demo/': { title: 'Fitxa d’exemple · Hebra', noindex: true },
  },
  en: {
    '/': { title: 'Hebra · What happens inside the fitting room', desc: 'Hebra measures what happens in your fashion store’s fitting room: which clothes are tried on and not sold, and why. A smart tag in every garment.' },
    '/probador/': { title: 'Fitting room: try-ons, sizes and lost sales · Hebra', desc: 'Which garments go into each room, which sell and why the rest stay behind. In-store alerts, a weekly report and tests against a control group.' },
    '/origen/': { title: 'Origin: supply chain traceability per garment · Hebra', desc: 'Each style’s supply chain in four stages, certificates with expiry alerts and environmental cost with Ecobalyse. For fashion brands with 1 to 5 stores.' },
    '/ficha/': { title: 'The garment page: its story on your phone · Hebra', desc: 'Tap a garment with a phone and its page opens: composition, care and origin for your customer, and fitting room data for you. No app needed.' },
    '/como-funciona/': { title: 'How Hebra’s smart garment tag works', desc: 'A tag in every garment, a store that recognises it on its own, and an action every Monday. Try the fitting room simulator.' },
    '/blog/': { title: 'Hebra blog: fitting rooms, sizes and origin in fashion', desc: 'What we learn about fitting rooms, sizes, origin and fashion stores.' },
    '/nosotros/': { title: 'About Hebra: mission, vision and values', desc: 'Hebra was born in Barcelona so fashion brands with their own stores know what happens in their fitting rooms and where what they sell comes from.' },
    '/contacto/': { title: 'Contact: book a Hebra demo', desc: 'Write to us and in half an hour we’ll show you the tag, the garment page and the fitting room data with real garments. We reply from clientes@hebraia.com.' },
    '/piloto/': { title: '8-week pilot in your fashion store · Hebra', desc: 'Eight weeks in one store to prove Hebra’s value with data: success criteria agreed in writing, a report every Monday and a control group.' },
    '/privacidad/': { title: 'Privacy policy · Hebra' },
    '/aviso-legal/': { title: 'Legal notice · Hebra' },
    '/cookies/': { title: 'Cookie policy · Hebra' },
    '/privacidad-ficha/': { title: 'Garment page privacy · Hebra' },
    '/gracias/': { title: 'Message sent · Hebra', noindex: true },
    '/p/demo/': { title: 'Example garment page · Hebra', noindex: true },
  },
};

/** Rutas que van al sitemap (las indexables), sin idioma. */
export const sitemapRoutes = Object.entries(seo.es).filter(([, e]) => !e.noindex).map(([r]) => r);
