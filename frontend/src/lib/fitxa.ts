/** Ajudes pures per a l'editor de la fitxa NFC (A). */
import type { ConfigFitxa, ConfigFitxaParcial, MotiuFitxa, SeccioFitxa } from '../api/types';

export const SECCIONS_FITXA: { clau: SeccioFitxa; nom: string; ajuda: string }[] = [
  { clau: 'talles', nom: 'Talles i ajust', ajuda: 'Les talles, com queda i el botó per demanar-ne una altra.' },
  { clau: 'composicio', nom: 'Composició', ajuda: 'Materials i percentatges.' },
  { clau: 'origen', nom: 'Origen', ajuda: 'D’on ve cada etapa. Només surt els dies que la prova d’origen ho permet.' },
  { clau: 'cura', nom: 'Cura de la peça', ajuda: 'Com rentar-la i guardar-la.' },
  { clau: 'combina', nom: 'Combina amb', ajuda: 'Altres peces que queden bé amb aquesta.' },
  { clau: 'faq', nom: 'Preguntes freqüents', ajuda: 'Dubtes habituals, amb la resposta.' },
];
export const nomSeccioFitxa = (s: SeccioFitxa) => SECCIONS_FITXA.find((x) => x.clau === s)?.nom ?? s;

export const MOTIUS_FITXA: { clau: MotiuFitxa; nom: string }[] = [
  { clau: 'talla', nom: 'No hi ha la meva talla' }, { clau: 'preu', nom: 'El preu' }, { clau: 'tall', nom: 'El tall o com queda' },
  { clau: 'qualitat', nom: 'La qualitat o el teixit' }, { clau: 'color', nom: 'El color' }, { clau: 'nomes_mirava', nom: 'Només mirava' }, { clau: 'altre', nom: 'Un altre motiu' },
];

export const IDIOMES_FITXA = ['ca', 'es', 'fr', 'en', 'de', 'it', 'pt'];

/** Mou un element d'una llista una posició amunt (-1) o avall (+1). */
export function mou<T>(llista: T[], i: number, d: -1 | 1): T[] {
  const j = i + d;
  if (j < 0 || j >= llista.length) return llista;
  const r = [...llista];
  [r[i], r[j]] = [r[j], r[i]];
  return r;
}

export const MAX_LOGO = 100 * 1024;
/** Valida el fitxer de logo abans de llegir-lo: PNG o SVG, ≤ 100 KB. */
export function validaLogo(f: { type: string; size: number }): string | null {
  if (!['image/png', 'image/svg+xml'].includes(f.type)) return 'El logo ha de ser un fitxer PNG o SVG.';
  if (f.size > MAX_LOGO) return `El logo fa ${Math.ceil(f.size / 1024)} KB: el màxim és 100 KB. Redueix-ne la mida o fes-lo servir en SVG.`;
  return null;
}

export const colorValid = (c: string) => /^#[0-9A-Fa-f]{6}$/.test(c);

function lum(hex: string): number {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
/** Contrast WCAG entre dos colors #RRGGBB (1-21). */
export function contrast(a: string, b: string): number {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

/** Els grups de primer nivell que una botiga pot personalitzar. */
export const GRUPS: (keyof ConfigFitxa)[] = ['seccions', 'accions', 'idiomes', 'textos', 'aparença', 'motius'];

/** Configuració efectiva = general + els grups que la botiga sobreescriu. */
export function combina(general: ConfigFitxa, botiga: ConfigFitxaParcial | null): ConfigFitxa {
  const r = structuredClone(general);
  if (!botiga) return r;
  for (const g of GRUPS) {
    const v = botiga[g];
    if (v === undefined) continue;
    if (Array.isArray(v)) (r as unknown as Record<string, unknown>)[g] = [...v];
    else Object.assign(r[g] as object, structuredClone(v));
  }
  return r;
}
