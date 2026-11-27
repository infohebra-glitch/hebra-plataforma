/** v0.9 (demo): devolucions online inventades i la comparativa amb el provador, com hebra/analitica/devolucions.py. */
import type * as T from '../api/types';
import { MODELS, arr, dies, type FiltreMock } from './dades';

const NOMS: Record<string, string> = {
  talla: 'Talla', tall: 'Tall o forma', preu: 'Preu', color: 'Color', qualitat: 'Qualitat o teixit', altre: 'Altre',
  diferent_foto: 'No era com a la foto o la descripció', defecte: 'Defecte o arribada malmesa',
  enviament: 'Enviament: tard o peça equivocada', canvi_opinio: 'Ha canviat d’opinió',
};
const NOMES_ONLINE = ['diferent_foto', 'defecte', 'enviament', 'canvi_opinio'];
const COMPARABLES = ['talla', 'tall', 'preu', 'color', 'qualitat', 'altre'];
const MIN = 5;

// Per setmana i model: quatre perfils (com el lot de prova): igual que al provador, la foto enganya, qualitat, va gran.
const PERFILS: Record<string, number>[] = [
  { 'talla:petita': 3, 'talla:gran': 0.5, tall: 0.5, qualitat: 0.5, canvi_opinio: 0.5 },
  { diferent_foto: 2.5, color: 1.5, 'talla:gran': 0.5, preu: 0.5, canvi_opinio: 0.5 },
  { qualitat: 2.5, 'talla:petita': 0.5, defecte: 1, canvi_opinio: 0.5 },
  { 'talla:gran': 2.5, tall: 1, enviament: 0.5, canvi_opinio: 1 },
];

export const mapaMock: T.CodiDevolucio[] = [
  { codi: 'talla pequeña', motiu: 'talla', sentit: 'petita', manual: false, unitats: 96, suggeriment: 'talla' },
  { codi: 'talla grande', motiu: 'talla', sentit: 'gran', manual: false, unitats: 41, suggeriment: 'talla' },
  { codi: 'no es como en la foto', motiu: 'diferent_foto', sentit: null, manual: false, unitats: 58, suggeriment: 'diferent_foto' },
  { codi: 'calidad', motiu: 'qualitat', sentit: null, manual: false, unitats: 52, suggeriment: 'qualitat' },
  { codi: 'color diferente', motiu: 'color', sentit: null, manual: false, unitats: 37, suggeriment: 'color' },
  { codi: 'ya no lo quiero', motiu: 'canvi_opinio', sentit: null, manual: false, unitats: 44, suggeriment: 'canvi_opinio' },
  { codi: 'no me favorece', motiu: 'tall', sentit: null, manual: false, unitats: 28, suggeriment: 'tall' },
  { codi: 'defectuoso', motiu: 'defecte', sentit: null, manual: false, unitats: 19, suggeriment: 'defecte' },
  { codi: 'r07', motiu: 'altre', sentit: null, manual: false, unitats: 3, suggeriment: null },
];

function coincidencia(p: Record<string, number>, o: Record<string, number>): number | null {
  const np = COMPARABLES.reduce((s, k) => s + (p[k] ?? 0), 0), no = COMPARABLES.reduce((s, k) => s + (o[k] ?? 0), 0);
  if (np < MIN || no < MIN) return null;
  return arr(COMPARABLES.reduce((s, k) => s + Math.min((p[k] ?? 0) / np, (o[k] ?? 0) / no), 0), 3);
}
const principal = (c: Record<string, number>, claus: string[]) => {
  const v = claus.filter((k) => c[k]).sort((a, b) => c[b] - c[a]);
  return v[0] ?? null;
};

export function provadorOnline(f: FiltreMock, nBotigues: number, nBotiguesTotal: number, model?: string): T.ProvadorOnline {
  const setmanes = Math.max(1, dies(f.des, f.fins).length / 7);
  const fp = Math.max(0.3, setmanes * (nBotigues / nBotiguesTotal));
  const prov: Record<string, number> = {}, onl: Record<string, number> = {};
  const sentit = { petita: 0, gran: 0 };
  const models: T.ModelProvadorOnline[] = [];
  const talles: T.TallaOnline[] = [];
  MODELS.forEach((m, i) => {
    if (model && m.model !== model) return;
    const cp: Record<string, number> = {}, co: Record<string, number> = {};
    for (const [k, v] of Object.entries(m.motius)) {
      if (k === 'nomes_mirava') continue;
      const n = Math.round((v ?? 0) * fp);
      if (n) { const c = k.startsWith('p-') ? 'altre' : k; cp[c] = (cp[c] ?? 0) + n; prov[c] = (prov[c] ?? 0) + n; }
    }
    const so = { petita: 0, gran: 0 };
    for (const [k, v] of Object.entries(PERFILS[i % 4])) {
      const n = Math.round(v * setmanes);
      if (!n) continue;
      const [c, s] = k.split(':');
      co[c] = (co[c] ?? 0) + n; onl[c] = (onl[c] ?? 0) + n;
      if (s) { so[s as 'petita' | 'gran'] += n; sentit[s as 'petita' | 'gran'] += n; }
    }
    if (so.petita + so.gran) {
      const t = m.talles[Math.floor(m.talles.length / 2)];
      talles.push({ model: m.model, nom: m.nom, talla: t, petita: so.petita, gran: so.gran, sense: 0 });
    }
    const c = coincidencia(cp, co);
    const pp = principal(cp, COMPARABLES), po = principal(co, Object.keys(NOMS)), poc = principal(co, COMPARABLES);
    const np = NOMS[pp ?? ''], no = NOMS[poc ?? ''];
    let lectura = 'Encara poques respostes per comparar-ho.';
    if (c !== null) {
      lectura = c >= 0.7 ? `Coincideix: als dos llocs el motiu principal és «${no}».`
        : c >= 0.5 ? `Coincideix a mitges: al provador sobretot «${np}», online «${no}».`
          : `No coincideix: al provador diuen «${np}» i online «${no}». El problema online pot ser un altre.`;
      if (so.petita + so.gran >= 3) lectura += ` Online, quan és la talla, va massa ${so.petita >= so.gran ? 'petita' : 'gran'}.`;
    }
    models.push({
      model: m.model, nom: m.nom,
      respostes_provador: Object.values(cp).reduce((s, n) => s + n, 0), devolucions_online: Object.values(co).reduce((s, n) => s + n, 0),
      motiu_provador: pp, motiu_online: po, provador: cp, online: co,
      nomes_online: NOMES_ONLINE.reduce((s, k) => s + (co[k] ?? 0), 0),
      coincidencia: c, divergent: c !== null && c < 0.5,
      talla_online: so, talla_provador: { petita: Math.round(fp * (i % 3)), gran: Math.round(fp * ((i + 1) % 3)) }, lectura,
    });
  });
  models.sort((a, b) => (a.coincidencia === null ? 1 : 0) - (b.coincidencia === null ? 1 : 0) || (a.coincidencia ?? 0) - (b.coincidencia ?? 0));
  const np = COMPARABLES.reduce((s, k) => s + (prov[k] ?? 0), 0);
  const noc = COMPARABLES.reduce((s, k) => s + (onl[k] ?? 0), 0);
  const nt = Object.values(onl).reduce((s, n) => s + n, 0);
  const coin = coincidencia(prov, onl);
  const divergents = models.filter((m) => m.divergent);
  const fr = (a: number, b: number) => (b ? arr(a / b, 3) : null);
  return {
    respostes_provador: np, devolucions_online: nt, nomes_online: nt - noc, pct_nomes_online: fr(nt - noc, nt), coincidencia: coin,
    categories: COMPARABLES.filter((k) => prov[k] || onl[k])
      .map((k) => ({ motiu: k, nom: NOMS[k], provador: prov[k] ?? 0, pct_provador: fr(prov[k] ?? 0, np), online: onl[k] ?? 0, pct_online: fr(onl[k] ?? 0, noc) }))
      .sort((a, b) => (b.pct_provador ?? 0) + (b.pct_online ?? 0) - (a.pct_provador ?? 0) - (a.pct_online ?? 0)),
    nomes_online_detall: NOMES_ONLINE.filter((k) => onl[k]).map((k) => ({ motiu: k, nom: NOMS[k], online: onl[k], pct: fr(onl[k], nt) })),
    talla_sentit: { online: sentit, provador: { petita: Math.round(fp * 9), gran: Math.round(fp * 7) } },
    models, talles, etiquetes: NOMS, minim: MIN,
    text: coin === null ? 'Encara poques respostes per comparar.'
      : `Els motius del provador i els de les devolucions online coincideixen en un ${Math.round(coin * 100)} %. `
        + (divergents.length ? `${divergents.length} models no coincideixen: ${divergents.slice(0, 3).map((m) => m.nom).join(', ')}.` : 'Cap model amb motius molt diferents.'),
    importat: { linies: 412, unitats: 431, des: '2026-09-01', fins: f.fins },
  };
}

export function mapa(): T.MapaDevolucions {
  return {
    codis: mapaMock,
    categories: Object.entries(NOMS).map(([clau, nom]) => ({ clau, nom, nomes_online: NOMES_ONLINE.includes(clau) })),
    importat: { linies: 412, unitats: 431, des: '2026-09-01', fins: '2026-11-29' },
  };
}
