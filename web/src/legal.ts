// Dades legals del titular de la web. Un sol lloc per omplir-les.
// Mentre un camp és buit, la línia corresponent no es mostra (mai es veuen claudàtors).
// Quan hi hagi SL: posar company, nif, address i registry.
import type { Lang } from './i18n';

export const LEGAL = {
  owner: 'Iscle Beltran Romeu',   // persona titular mentre l'SL està en constitució
  company: '',                    // p. ex. 'Hebra Trace, S.L.' quan existeixi
  nif: '',                        // NIF del titular (obligatori per l'LSSI)
  address: '',                    // adreça completa amb codi postal
  registry: '',                   // dades del Registre Mercantil, quan n'hi hagi
  updated: { es: '27 de noviembre de 2026', ca: '27 de novembre de 2026', en: '27 November 2026' },
};

const W = {
  es: { inForm: 'sociedad en constitución', brand: 'la marca', hosting: 'Vercel Inc. (alojamiento de la web y del formulario)', mail: 'ImprovMX y Google (Gmail), correo electrónico', noStats: 'Hoy <strong>no usamos ninguna herramienta de estadísticas</strong>. Si un día la usamos, será una que no use cookies ni guarde nada en tu dispositivo, y lo diremos aquí antes de activarla.' },
  ca: { inForm: 'societat en constitució', brand: 'la marca', hosting: 'Vercel Inc. (allotjament de la web i del formulari)', mail: 'ImprovMX i Google (Gmail), correu electrònic', noStats: 'Avui <strong>no fem servir cap eina d’estadístiques</strong>. Si algun dia en fem servir una, serà sense galetes i sense guardar res al teu dispositiu, i ho direm aquí abans d’activar-la.' },
  en: { inForm: 'company being incorporated', brand: 'the brand', hosting: 'Vercel Inc. (website and form hosting)', mail: 'ImprovMX and Google (Gmail), email', noStats: 'Today we <strong>use no analytics tool at all</strong>. If we ever use one, it will not use cookies or store anything on your device, and we will say so here before turning it on.' },
} as const;

export function ownerName(lang: Lang) {
  return LEGAL.company || `${LEGAL.owner} (Hebra, ${W[lang].inForm})`;
}

/** Omple els textos legals: substitueix els buits pel que sabem i treu el que encara no tenim. */
export function fillLegal(html: string, lang: Lang): string {
  const w = W[lang];
  const pend = (inner: string) => new RegExp(`<span class="pend">\\[${inner}\\]</span>`, 'g');
  let h = html;
  // Data
  h = h.replace(pend('(fecha de publicación|data de publicació|publication date)'), LEGAL.updated[lang]);
  // Titular
  h = h.replace(pend('(RAZÓN SOCIAL, S\\.L\\.|RAÓ SOCIAL, S\\.L\\.|COMPANY NAME, S\\.L\\.)'), ownerName(lang));
  // Línies de NIF, domicili i registre: es mostren només si hi ha dada
  h = h.replace(/<li><strong>[^<]*NIF\)?:<\/strong>[^<]*<span class="pend">\[NIF\]<\/span><\/li>/g, LEGAL.nif ? `<li><strong>NIF:</strong> ${LEGAL.nif}</li>` : '');
  h = h.replace(/, (NIF|Tax ID) <span class="pend">\[NIF\]<\/span>/g, LEGAL.nif ? `, $1 ${LEGAL.nif}` : "");
  h = h.replace(/<li><strong>[^<]*:<\/strong> <span class="pend">\[(DIRECCIÓN COMPLETA|ADREÇA COMPLETA|FULL ADDRESS)\]<\/span>, <span class="pend">\[[^\]]+\]<\/span>[^<]*<\/li>/g,
    (m) => LEGAL.address ? m.replace(/<span class="pend">\[[^\]]+\]<\/span>, <span class="pend">\[[^\]]+\]<\/span>[^<]*/, LEGAL.address) : '');
  h = h.replace(/<li><strong>[^<]*(registrales|registrals|Registry details)[^<]*:<\/strong>.*?<\/li>/g, LEGAL.registry ? (m) => m.replace(/:<\/strong>.*<\/li>/, `:</strong> ${LEGAL.registry}</li>`) : '');
  // Adreça dins d'un paràgraf (privacitat): treure la frase si no hi ha adreça
  h = h.replace(/<br\s*\/?>\s*<strong>[^<]*(Dirección|Adreça|Address):?<\/strong>:? ?<span class="pend">\[[^\]]+\]<\/span>, <span class="pend">\[[^\]]+\]<\/span>[^<]*/g, LEGAL.address ? (m) => m.replace(/<span class="pend">.*$/, LEGAL.address) : '');
  h = h.replace(/(Dirección|Adreça|Address): <span class="pend">\[[^\]]+\]<\/span>, <span class="pend">\[[^\]]+\]<\/span>[^<]*/g, LEGAL.address ? `$1: ${LEGAL.address}` : '');
  // Proveïdors
  h = h.replace(pend('(PROVEEDOR DE ALOJAMIENTO|PROVEÏDOR D\'ALLOTJAMENT|HOSTING PROVIDER)[^\\]]*'), 'Vercel Inc.');
  h = h.replace(pend('(PROVEEDOR DE CORREO|PROVEÏDOR DE CORREU|EMAIL PROVIDER)[^\\]]*'), lang === 'en' ? 'ImprovMX and Google (Gmail)' : lang === 'ca' ? 'ImprovMX i Google (Gmail)' : 'ImprovMX y Google (Gmail)');
  // Estadístiques: avui no n'hi ha
  h = h.replace(/<tr><td><span class="pend">\[(PROVEEDOR DE ESTADÍSTICAS|PROVEÏDOR D'ESTADÍSTIQUES|ANALYTICS PROVIDER)[^\]]*\]<\/span><\/td>.*?<\/tr>/g, '');
  h = h.replace(/<p>[^<]*<span class="pend">\[(PROVEEDOR DE ESTADÍSTICAS|PROVEÏDOR D'ESTADÍSTIQUES|ANALYTICS PROVIDER)\]<\/span>.*?<\/p>/g, `<p>${w.noStats}</p>`);
  // Altres
  h = h.replace(pend('(MARCA|BRAND)'), w.brand);
  h = h.replace(pend('30'), '30');
  h = h.replace(/<span class="pend">(Nota para el equipo|Nota per a l'equip|Note for the team)[^<]*<\/span>/g, '');
  return h;
}
