// Idiomas de la web. El castellano va en la raíz; catalán en /ca/ e inglés en /en/.
export const langs = ['es', 'ca', 'en'] as const;
export type Lang = (typeof langs)[number];
export const langName: Record<Lang, string> = { es: 'Español', ca: 'Català', en: 'English' };
export const langShort: Record<Lang, string> = { es: 'ES', ca: 'CA', en: 'EN' };

/** Ruta de una página en un idioma: path('ca', '/probador/') → '/ca/probador/' */
export function path(lang: Lang, route = '/') {
  const r = route.startsWith('/') ? route : `/${route}`;
  return lang === 'es' ? r : `/${lang}${r}`;
}

/** Elige el texto del idioma: pick(lang, { es, ca, en }) */
export function pick<T>(lang: Lang, v: Record<Lang, T>): T {
  return v[lang];
}

export const contacts = [
  { name: 'Hebra', email: 'clientes@hebraia.com' },
];
// Clave pública de Web3Forms (web3forms.com, gratis). Vacía: el formulario abre el correo del visitante.
export const formKey = '';
export const mainEmail = 'clientes@hebraia.com';

export const ui = {
  es: {
    nav: [['/probador/', 'Probador'], ['/origen/', 'Origen'], ['/ficha/', 'La ficha'], ['/como-funciona/', 'Cómo funciona'], ['/blog/', 'Blog'], ['/nosotros/', 'Nosotros']],
    contact: 'Contacto',
    demo: 'Pedir una demo',
    menu: 'Menú',
    close: 'Cerrar',
    navMain: 'Principal', navFoot: 'Pie de página', langLabel: 'Idioma',
    home: 'Inicio',
    footClaim: 'La prenda ya sabe dónde ha estado. Hebra hace que la marca lo sepa.',
    pilot: 'El piloto',
    privacy: 'Privacidad',
    legal: 'Aviso legal',
    cookies: 'Cookies',
    fichaDemo: 'Ver una ficha de ejemplo',
    write: 'Escríbenos',
    base: 'Hebra, Barcelona. Trace the truth.',
    ctaTitle: 'Hablemos de <em>tu marca.</em>',
    ctaText: 'En media hora te enseñamos la etiqueta, la ficha y los datos con prendas reales. Y vemos juntos por dónde empezar en tu tienda.',
    ctaSecondary: 'Ver la ficha',
    titleHome: 'Hebra · Lo que pasa dentro del probador',
  },
  ca: {
    nav: [['/probador/', 'Emprovador'], ['/origen/', 'Origen'], ['/ficha/', 'La fitxa'], ['/como-funciona/', 'Com funciona'], ['/blog/', 'Blog'], ['/nosotros/', 'Nosaltres']],
    contact: 'Contacte',
    demo: 'Demanar una demo',
    menu: 'Menú',
    close: 'Tancar',
    navMain: 'Principal', navFoot: 'Peu de pàgina', langLabel: 'Idioma',
    home: 'Inici',
    footClaim: 'La peça ja sap on ha estat. Hebra fa que la marca ho sàpiga.',
    pilot: 'El pilot',
    privacy: 'Privacitat',
    legal: 'Avís legal',
    cookies: 'Galetes',
    fichaDemo: 'Veure una fitxa d’exemple',
    write: 'Escriu-nos',
    base: 'Hebra, Barcelona. Trace the truth.',
    ctaTitle: 'Parlem de <em>la teva marca.</em>',
    ctaText: 'En mitja hora t’ensenyem l’etiqueta, la fitxa i les dades amb peces reals. I veiem junts per on començar a la teva botiga.',
    ctaSecondary: 'Veure la fitxa',
    titleHome: 'Hebra · El que passa dins l’emprovador',
  },
  en: {
    nav: [['/probador/', 'Fitting room'], ['/origen/', 'Origin'], ['/ficha/', 'The garment page'], ['/como-funciona/', 'How it works'], ['/blog/', 'Blog'], ['/nosotros/', 'About']],
    contact: 'Contact',
    demo: 'Book a demo',
    menu: 'Menu',
    close: 'Close',
    navMain: 'Main', navFoot: 'Footer', langLabel: 'Language',
    home: 'Home',
    footClaim: 'The garment already knows where it has been. Hebra lets the brand know too.',
    pilot: 'The pilot',
    privacy: 'Privacy',
    legal: 'Legal notice',
    cookies: 'Cookies',
    fichaDemo: 'See an example garment page',
    write: 'Write to us',
    base: 'Hebra, Barcelona. Trace the truth.',
    ctaTitle: 'Let’s talk about <em>your brand.</em>',
    ctaText: 'In half an hour we show you the tag, the garment page and the data with real garments. Then we work out together where to start in your store.',
    ctaSecondary: 'See the garment page',
    titleHome: 'Hebra · What happens inside the fitting room',
  },
} satisfies Record<Lang, Record<string, unknown>>;
