/**
 * Formats en català (Intl 'ca-ES'). Tot el tauler passa per aquí perquè les
 * xifres es vegin igual a tot arreu: «34 %», «1.234», «69 €», «+3 punts».
 */
const LOCALE = 'ca-ES';
const GUIO = '—';

// «always» força el punt de milers també a 4 xifres (1.234), que el CLDR català
// no posa per defecte en alguns navegadors.
function nf(o: Intl.NumberFormatOptions): Intl.NumberFormat {
  try {
    return new Intl.NumberFormat(LOCALE, { useGrouping: 'always', ...o } as Intl.NumberFormatOptions);
  } catch {
    return new Intl.NumberFormat(LOCALE, o);
  }
}

const fEnter = nf({ maximumFractionDigits: 0 });
const fDecimal = nf({ minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fPct = nf({ style: 'percent', maximumFractionDigits: 0 });
const fPct1 = nf({ style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fEur = nf({ style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
const fEur2 = nf({ style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2 });

const buit = (x: number | null | undefined): x is null | undefined => x === null || x === undefined || Number.isNaN(x);

/** 1234 → «1.234». */
export const enter = (x: number | null | undefined): string => (buit(x) ? GUIO : fEnter.format(x));

/** 1.6 → «1,6». */
export const decimal = (x: number | null | undefined): string => (buit(x) ? GUIO : fDecimal.format(x));

/** Fracció 0-1 → «34 %». `decimals` = 1 per a valors petits (3,7 %). */
export const pct = (x: number | null | undefined, decimals: 0 | 1 = 0): string =>
  buit(x) ? GUIO : (decimals ? fPct1 : fPct).format(x);

/** Diferència de fraccions en punts percentuals: 0.03 → «+3 punts». */
export function punts(x: number | null | undefined, decimals: 0 | 1 = 0): string {
  if (buit(x)) return GUIO;
  const v = x * 100;
  const arrodonit = Number(v.toFixed(decimals));
  const signe = arrodonit > 0 ? '+' : arrodonit < 0 ? '−' : '';
  const n = decimals ? fDecimal.format(Math.abs(arrodonit)) : fEnter.format(Math.abs(arrodonit));
  return `${signe}${n} ${Math.abs(arrodonit) === 1 ? 'punt' : 'punts'}`;
}

/** Euros sense cèntims: 69 → «69 €». */
export const eur = (x: number | null | undefined, cèntims = false): string =>
  buit(x) ? GUIO : (cèntims ? fEur2 : fEur).format(x);

/** Segons → «92 s» o «5 min 40 s». */
export function segons(s: number | null | undefined): string {
  if (buit(s)) return GUIO;
  const r = Math.round(s);
  if (r < 120) return `${fEnter.format(r)} s`;
  const m = Math.floor(r / 60);
  const rest = r % 60;
  return rest ? `${m} min ${rest} s` : `${m} min`;
}

/** «X de Y» per mostrar sempre el denominador. */
export const deCada = (num: number, den: number): string => `${enter(num)} de ${enter(den)}`;

/** p-valor en paraules planeres. */
export function pValorEnParaules(p: number | null | undefined): string {
  if (buit(p)) return 'Encara no es pot calcular.';
  const pTxt = p < 0.001 ? 'menys de 0,001' : nf({ maximumFractionDigits: p < 0.01 ? 3 : 2 }).format(p);
  if (p < 0.01) return `Molt improbable que sigui casualitat (p = ${pTxt}).`;
  if (p < 0.05) return `Poc probable que sigui casualitat (p = ${pTxt}).`;
  if (p < 0.2) return `Podria ser casualitat: encara no és concloent (p = ${pTxt}).`;
  return `Amb aquestes dades, la diferència pot ser perfectament casualitat (p = ${pTxt}).`;
}

// ── Dates ────────────────────────────────────────────────────────────────

/** «AAAA-MM-DD» → Date al migdia local (evita salts de dia per zona horària). */
export function dataLocal(iso: string): Date {
  const [a, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(a, (m ?? 1) - 1, d ?? 1, 12);
}

export function isoData(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const fDiaCurt = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short' });
const fDiaSetmana = new Intl.DateTimeFormat(LOCALE, { weekday: 'short', day: 'numeric' });
const fDiaLlarg = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'long', year: 'numeric' });
const fHora = new Intl.DateTimeFormat(LOCALE, { hour: '2-digit', minute: '2-digit' });

/** «16 de nov.» */
export const diaCurt = (iso: string | null | undefined): string => (iso ? fDiaCurt.format(dataLocal(iso)) : GUIO);
/** «dl. 16» */
export const diaSetmana = (iso: string): string => fDiaSetmana.format(dataLocal(iso));
/** «16 de novembre del 2026» */
export const diaLlarg = (iso: string | null | undefined): string => (iso ? fDiaLlarg.format(dataLocal(iso)) : GUIO);
/** «12:05» d'una hora ISO. */
export const hora = (iso: string): string => fHora.format(new Date(iso));

/** «del 16 al 22 de nov.» */
export function rang(des: string, fins: string): string {
  return `del ${diaCurt(des)} al ${diaCurt(fins)}`;
}

export const DIES_SETMANA = ['dl.', 'dt.', 'dc.', 'dj.', 'dv.', 'ds.', 'dg.'];
export const DIES_SETMANA_LLARG = ['dilluns', 'dimarts', 'dimecres', 'dijous', 'divendres', 'dissabte', 'diumenge'];

/** Fa servir el singular o el plural: plural(1,'prova','proves'). */
export const plural = (n: number, u: string, p: string): string => `${enter(n)} ${n === 1 ? u : p}`;
