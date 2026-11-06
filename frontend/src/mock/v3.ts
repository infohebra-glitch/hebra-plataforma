/**
 * Mode demostració, rutes de la v0.3 (docs/ESPECIFICACIO-v3.md): fitxa NFC
 * configurable, provadors en directe, sessions, estoc parat amb tasques,
 * informes lliurats i programats, integracions. Estat en memòria.
 */
import type * as T from '../api/types';
import { dataLocal, isoData } from '../lib/format';
import { properaExecucio } from '../lib/programacio';
import { BOTIGUES, MODELS, ORIGENS, arr, avui, conv, cub, defModel, dies, estat, sumaCompres, sumaProves, type FiltreMock } from './dades';
import { atzar } from './estadistica';

const ara = () => new Date();
const fa = (min: number) => new Date(Date.now() - min * 60000).toISOString();
const nomBotiga = (id: string | null | undefined) => BOTIGUES.find((b) => b.id === id)?.nom.split(' · ')[0] ?? id ?? '';
const suma = (iso: string, n: number) => { const d = dataLocal(iso); d.setDate(d.getDate() + n); return isoData(d); };
const gtinDe = (model: string, talla: string) => {
  const m = defModel(model)!;
  return `84${String(1000000000 + MODELS.indexOf(m) * 100 + m.talles.indexOf(talla)).padStart(11, '0')}`;
};
/** El flux fals (index.ts) s'hi connecta per avisar de les tasques noves o tancades. */
export const avisos = { tasca: (_t: T.Tasca): void => {} };

// ── Tasques ──────────────────────────────────────────────────────────────
let seguentTasca = 6;
export const tasquesMock: T.Tasca[] = [
  { id: 5, botiga_id: 'BCN-01', tipus: 'moure_a_sala', titol: 'Treure a la sala la sobrecamisa de cotó en XS', detall: 'No s’ha provat mai a la botiga: potser és al magatzem.', gtin: gtinDe('SB-25-CRU', 'XS'), unitats: 1, botiga_desti: null, estat: 'pendent', creada: fa(60 * 20), feta: null },
  { id: 4, botiga_id: 'BCN-01', tipus: 'traspassar', titol: 'Traspassar 3 pantalons de lli (44) a Madrid', detall: 'A Madrid s’ha provat 9 vegades aquest mes.', gtin: gtinDe('PL-26-TER', '44'), unitats: 3, botiga_desti: 'MAD-01', estat: 'pendent', creada: fa(60 * 26), feta: null },
  { id: 3, botiga_id: 'BCN-01', tipus: 'recompte', titol: 'Recomptar els texans rectes', detall: 'L’RFID i el TPV no quadren en 2 unitats.', gtin: null, unitats: null, botiga_desti: null, estat: 'pendent', creada: fa(60 * 3), feta: null },
  { id: 2, botiga_id: 'MAD-01', tipus: 'promocio', titol: 'Posar el vestit de viscosa (L) a l’aparador', detall: null, gtin: gtinDe('VV-26-VRD', 'L'), unitats: 2, botiga_desti: null, estat: 'pendent', creada: fa(60 * 30), feta: null },
  { id: 1, botiga_id: 'BCN-01', tipus: 'altre', titol: 'Canviar l’etiqueta trencada de la camisa de lli M', detall: null, gtin: null, unitats: 1, botiga_desti: null, estat: 'feta', creada: fa(60 * 50), feta: fa(60 * 45) },
];

export function creaTasca(c: T.NovaTasca): T.Tasca {
  const t: T.Tasca = { id: seguentTasca++, botiga_id: c.botiga_id, tipus: c.tipus, titol: c.titol, detall: c.detall ?? null, gtin: c.gtin ?? null, unitats: c.unitats ?? null, botiga_desti: c.botiga_desti ?? null, estat: 'pendent', creada: ara().toISOString(), feta: null };
  tasquesMock.unshift(t);
  avisos.tasca(t);
  return t;
}

// ── Estoc parat amb suggeriments ─────────────────────────────────────────
interface DefParat { botiga: string; model: string; talla: string; unitats: number; dies: number; provesAltres: number; vendesAltres: number; provesAqui: number; accio: T.AccioSuggeriment; desti?: string }
const PARAT: DefParat[] = [
  { botiga: 'BCN-01', model: 'PL-26-TER', talla: '44', unitats: 4, dies: 34, provesAltres: 9, vendesAltres: 3, provesAqui: 0, accio: 'traspassar', desti: 'MAD-01' },
  { botiga: 'BCN-01', model: 'SB-25-CRU', talla: 'XS', unitats: 1, dies: 27, provesAltres: 0, vendesAltres: 0, provesAqui: 0, accio: 'moure_a_sala' },
  { botiga: 'BCN-01', model: 'VV-26-VRD', talla: 'L', unitats: 2, dies: 23, provesAltres: 2, vendesAltres: 0, provesAqui: 6, accio: 'revisar' },
  { botiga: 'BCN-01', model: 'JM-24-GRF', talla: 'XL', unitats: 3, dies: 41, provesAltres: 12, vendesAltres: 4, provesAqui: 1, accio: 'traspassar', desti: 'GIR-01' },
  { botiga: 'BCN-01', model: 'FA-26-BLA', talla: 'XS', unitats: 2, dies: 66, provesAltres: 0, vendesAltres: 0, provesAqui: 0, accio: 'retornar' },
  { botiga: 'GIR-01', model: 'TX-26-IND', talla: '36', unitats: 2, dies: 29, provesAltres: 7, vendesAltres: 2, provesAqui: 0, accio: 'traspassar', desti: 'BCN-01' },
  { botiga: 'GIR-01', model: 'VV-26-VRD', talla: 'XS', unitats: 3, dies: 38, provesAltres: 4, vendesAltres: 0, provesAqui: 5, accio: 'promocio' },
  { botiga: 'GIR-01', model: 'PL-26-TER', talla: '36', unitats: 2, dies: 24, provesAltres: 0, vendesAltres: 0, provesAqui: 0, accio: 'moure_a_sala' },
  { botiga: 'MAD-01', model: 'CL-24-NAT', talla: 'XS', unitats: 2, dies: 22, provesAltres: 6, vendesAltres: 3, provesAqui: 0, accio: 'moure_a_sala' },
  { botiga: 'MAD-01', model: 'SB-25-CRU', talla: 'XL', unitats: 3, dies: 71, provesAltres: 1, vendesAltres: 0, provesAqui: 0, accio: 'retornar' },
  { botiga: 'MAD-01', model: 'VV-26-VRD', talla: 'M', unitats: 3, dies: 31, provesAltres: 3, vendesAltres: 0, provesAqui: 8, accio: 'promocio' },
];

function textSuggeriment(p: DefParat): string {
  const nom = defModel(p.model)!.nom.toLowerCase();
  switch (p.accio) {
    case 'traspassar': return `Traspassar ${p.unitats === 1 ? '1 unitat' : `${p.unitats} unitats`} a ${nomBotiga(p.desti)}: allà s’ha provat ${p.provesAltres} vegades i se n’han venut ${p.vendesAltres}.`;
    case 'moure_a_sala': return `No s’ha provat mai aquí. Comprova que sigui a la sala i ben visible (potser és al magatzem).`;
    case 'revisar': return `S’ha provat ${p.provesAqui} vegades i no se n’ha venut cap: mira els motius a la fitxa del ${nom} abans de rebaixar-lo.`;
    case 'promocio': return `Es prova (${p.provesAqui} vegades) però no es ven. Prova d’ensenyar-lo a l’aparador o en una promoció petita.`;
    default: return `Fa ${p.dies} dies que no es mou enlloc: valora retornar-lo al magatzem central.`;
  }
}

export const TITOLS_ACCIO: Record<T.AccioSuggeriment, string> = {
  traspassar: 'Traspassar', moure_a_sala: 'Treure a la sala', promocio: 'Promoció', retornar: 'Retornar', revisar: 'Revisar',
};

export function parat(f: FiltreMock): { parat: T.EstocParat[]; resum_parat: T.ResumParat } {
  const files = PARAT.filter((p) => f.botigues.includes(p.botiga)).map((p) => {
    const m = defModel(p.model)!;
    const gtin = gtinDe(p.model, p.talla);
    const tasca = tasquesMock.find((t) => t.gtin === gtin && t.botiga_id === p.botiga && t.estat === 'pendent') ?? null;
    return {
      gtin, model: m.model, nom: m.nom, talla: p.talla, unitats: p.unitats, dies_sense_activitat: p.dies,
      color: m.color, categoria: m.categoria, botiga_id: p.botiga, valor_eur: p.unitats * m.preu, dies_parat: p.dies,
      darrera_prova: p.provesAqui ? fa(60 * 24 * (p.dies + 3)) : null, darrera_venda: p.accio === 'moure_a_sala' ? null : fa(60 * 24 * (p.dies + 9)),
      proves_altres_botigues: p.provesAltres, vendes_altres_botigues: p.vendesAltres,
      suggeriment: { accio: p.accio, text: textSuggeriment(p), botiga_desti: p.desti ?? null },
      tasca,
    } satisfies T.EstocParat;
  });
  const cats = new Map<string, { unitats: number; valor_eur: number }>();
  for (const x of files) { const c = cats.get(x.categoria!) ?? { unitats: 0, valor_eur: 0 }; c.unitats += x.unitats; c.valor_eur += x.valor_eur!; cats.set(x.categoria!, c); }
  return {
    parat: files,
    resum_parat: {
      unitats: files.reduce((s, x) => s + x.unitats, 0), valor_eur: files.reduce((s, x) => s + (x.valor_eur ?? 0), 0),
      per_categoria: [...cats.entries()].map(([categoria, v]) => ({ categoria, ...v })).sort((a, b) => b.valor_eur - a.valor_eur),
    },
  };
}

export function paratCsv(f: FiltreMock, categoria: string | null): string {
  const files = parat(f).parat.filter((x) => !categoria || x.categoria === categoria);
  const esc = (v: unknown) => { const s = String(v ?? ''); return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const cap = ['botiga', 'gtin', 'model', 'nom', 'color', 'talla', 'categoria', 'unitats', 'valor_eur', 'dies_parat', 'suggeriment'];
  return [cap.join(';'), ...files.map((x) => [x.botiga_id, x.gtin, x.model, x.nom, x.color, x.talla, x.categoria, x.unitats, x.valor_eur, x.dies_parat, x.suggeriment?.text].map(esc).join(';'))].join('\n');
}

// ── Disponibilitat en altres botigues (A.5) ──────────────────────────────
export function altresBotigues(model: string, talla: string, botigaPropia = 'BCN-01'): T.AltraBotiga[] {
  const r = atzar(`ab${model}${talla}`);
  return BOTIGUES.filter((b) => b.id !== botigaPropia).map((b) => ({ botiga_id: b.id, nom: nomBotiga(b.id), unitats: Math.floor(r() * 4) })).filter((x) => x.unitats > 0);
}

// ── Provadors en directe ─────────────────────────────────────────────────
const CABINES: { id: string; botiga: string; nom: string }[] = [
  { id: 'BCN-01-C1', botiga: 'BCN-01', nom: 'Cabina 1' }, { id: 'BCN-01-C2', botiga: 'BCN-01', nom: 'Cabina 2' }, { id: 'BCN-01-C3', botiga: 'BCN-01', nom: 'Cabina 3' },
  { id: 'MAD-01-C1', botiga: 'MAD-01', nom: 'Cabina 1' }, { id: 'MAD-01-C2', botiga: 'MAD-01', nom: 'Cabina 2' },
];
let comptadorEpc = 100;
function pecesAleatories(n: number, llavor: string): T.PecaCabina[] {
  const r = atzar(llavor);
  const primer = MODELS[Math.floor(r() * MODELS.length)];
  return Array.from({ length: n }, (_, i) => {
    // De tant en tant, la mateixa peça en dues talles (dubte de talla).
    const m = i === 1 && r() < 0.35 ? primer : i === 0 ? primer : MODELS[Math.floor(r() * MODELS.length)];
    const talla = m.talles[Math.min(m.talles.length - 1, Math.floor(r() * m.talles.length))];
    return { epc: `3034F8A1C2000000${String(comptadorEpc++).padStart(8, '0')}`, model: m.model, nom: m.nom, talla, color: m.color, des_de: fa(r() * 4) };
  });
}

const cabinesEstat: T.CabinaDirecte[] = CABINES.map((c, i) => {
  const estatInicial: T.EstatCabinaDirecte = (['ocupada', 'lliure', 'ocupada', 'porta_oberta', 'sense_dades'] as const)[i];
  const peces = estatInicial === 'ocupada' ? pecesAleatories(i === 0 ? 3 : 2, `ini${c.id}`) : estatInicial === 'porta_oberta' ? pecesAleatories(1, `ini${c.id}`) : [];
  const r = atzar(`avui${c.id}`);
  const sessions = estatInicial === 'sense_dades' ? 0 : 8 + Math.floor(r() * 10);
  return {
    cabina_id: c.id, nom: c.nom, botiga_id: c.botiga, estat: estatInicial,
    des_de: estatInicial === 'sense_dades' ? fa(60 * 3.2) : fa(1 + i * 2.3), peces,
    peticions_obertes: c.id === 'BCN-01-C1' ? 1 : 0,
    avui: { sessions, proves: Math.round(sessions * 2.2), durada_mitjana_s: sessions ? 260 + Math.floor(r() * 120) : null },
  };
});

/** Avança una cabina a l'estat següent (per al flux fals). Torna la cabina canviada. */
let passos = 0;
export function avancaCabina(): T.CabinaDirecte {
  const vives = cabinesEstat.filter((c) => c.estat !== 'sense_dades');
  const c = vives[passos++ % vives.length];
  const r = atzar(`pas${passos}`);
  if (c.estat === 'lliure') {
    c.estat = 'ocupada'; c.peces = pecesAleatories(1 + Math.floor(r() * 3), `p${passos}`);
  } else if (c.estat === 'ocupada') {
    if (r() < 0.5 && c.peces.length < 4) c.peces = [...c.peces, ...pecesAleatories(1, `q${passos}`)];
    else { c.estat = 'porta_oberta'; c.peces = c.peces.slice(0, Math.max(0, c.peces.length - 1)); }
    if (r() < 0.25) c.peticions_obertes = 1;
  } else {
    c.estat = 'lliure'; c.peces = []; c.peticions_obertes = 0;
    c.avui = { sessions: c.avui.sessions + 1, proves: c.avui.proves + 2, durada_mitjana_s: c.avui.durada_mitjana_s ?? 300 };
  }
  c.des_de = ara().toISOString();
  return { ...c, peces: [...c.peces] };
}

export function provadorsDirecte(botigues: string[]): T.ProvadorsDirecte {
  const cab = cabinesEstat.filter((c) => botigues.includes(c.botiga_id)).map((c) => ({ ...c, peces: [...c.peces] }));
  return {
    generat: ara().toISOString(), cabines: cab,
    resum: {
      ocupades: cab.filter((c) => c.estat === 'ocupada').length, lliures: cab.filter((c) => c.estat === 'lliure').length,
      sessions_avui: cab.reduce((s, c) => s + c.avui.sessions, 0), proves_avui: cab.reduce((s, c) => s + c.avui.proves, 0),
    },
  };
}

// ── Sessions (C) ─────────────────────────────────────────────────────────
export function sessions(f: FiltreMock): T.Sessions {
  const c = cub(f);
  const proves = sumaProves(c), compres = sumaCompres(c);
  const n = Math.max(1, Math.round(proves / 2.3));
  const rep = [0.31, 0.29, 0.2, 0.12, 0.08];
  const convs = [0.28, 0.39, 0.47, 0.53, 0.58];
  const mp = (s: number) => s < 10;
  const per_nombre_peces = rep.map((p, i) => {
    const s = Math.round(n * p), ac = Math.round(s * convs[i]);
    return { peces: i === 4 ? '5+' : String(i + 1), sessions: s, amb_compra: ac, conversio_sessio: s ? arr(ac / s) : null, unitats_comprades: Math.round(ac * (1 + i * 0.25)), mostra_petita: mp(s) };
  });
  const factor = n / 250;
  const parells: [string, string, number, number, number][] = [
    ['CL-24-NAT', 'TX-26-IND', 18, 2.1, 0.33], ['JM-24-GRF', 'TX-26-IND', 14, 1.8, 0.29], ['VV-26-VRD', 'FA-26-BLA', 9, 1.6, 0.11],
    ['CL-24-NAT', 'PL-26-TER', 11, 1.4, 0.36], ['SB-25-CRU', 'TX-26-IND', 7, 1.3, 0.29], ['JM-24-GRF', 'PL-26-TER', 6, 0.9, 0.17],
  ];
  const provades_juntes = parells.map(([a, b, s, lift, cj]) => {
    const ses = Math.max(3, Math.round(s * factor));
    return { model_a: a, nom_a: defModel(a)!.nom, model_b: b, nom_b: defModel(b)!.nom, sessions: ses, lift, conversio_conjunta: cj, mostra_petita: mp(ses) };
  });
  const dubtes = MODELS.filter((m) => m.model !== 'FA-26-BLA').map((m) => {
    const r = atzar(`dub${m.model}${f.des}`);
    const ses = Math.max(1, Math.round((m.model === 'TX-26-IND' ? 14 : m.model === 'VV-26-VRD' ? 11 : 3 + r() * 6) * factor));
    const pct = m.model === 'TX-26-IND' ? 0.24 : m.model === 'VV-26-VRD' ? 0.19 : 0.04 + r() * 0.08;
    return { m, ses, pct };
  });
  const parells_talla = dubtes.flatMap(({ m, ses }) => parellsModel(m.model, ses));
  const per_model = dubtes.map(({ m, ses, pct }) => ({ model: m.model, nom: m.nom, sessions_dubte: ses, pct_sessions_model: arr(pct, 2), talla_mes_comprada: talleMesComprada(parellsModel(m.model, ses)), mostra_petita: mp(ses) }))
    .sort((a, b) => b.sessions_dubte - a.sessions_dubte);
  const totalDubte = per_model.reduce((s, x) => s + x.sessions_dubte, 0);
  const durades: [string, number, number][] = [['<2 min', 0.18, 0.12], ['2-5 min', 0.41, 0.36], ['5-10 min', 0.31, 0.52], ['>10 min', 0.1, 0.44]];
  const hores = [10, 11, 12, 13, 14, 16, 17, 18, 19, 20];
  const pesH = [0.05, 0.09, 0.13, 0.11, 0.06, 0.08, 0.13, 0.15, 0.13, 0.07];
  return {
    kpi: { sessions: n, peces_per_sessio_mitjana: arr(proves / n, 1), peces_per_sessio_mediana: 2, durada_mitjana_s: 342, pct_sessions_amb_compra: arr(Math.min(0.9, (compres / n) * 0.78), 2) },
    per_nombre_peces,
    provades_juntes,
    mateix_model_diferent_talla: { sessions: totalDubte, pct_sessions: arr(totalDubte / n, 2), parells_talla: parells_talla.sort((a, b) => b.sessions - a.sessions).slice(0, 8), per_model },
    per_durada: durades.map(([tram, p, cv]) => { const s = Math.round(n * p); return { tram, sessions: s, conversio_sessio: cv, mostra_petita: mp(s) }; }),
    per_hora: hores.map((hora, i) => { const s = Math.round(n * pesH[i]); return { hora, sessions: s, conversio_sessio: arr(0.3 + (hora >= 17 ? 0.12 : 0) + atzar(`h${hora}`)() * 0.08, 2), mostra_petita: mp(s) }; }),
  };
}

function parellsModel(model: string, sessionsTotal: number): T.ParellTalla[] {
  const m = defModel(model)!;
  const centre = m.pesTalla.indexOf(Math.max(...m.pesTalla));
  const pairs = [[centre - 1, centre], [centre, centre + 1]].filter(([a, b]) => a >= 0 && b < m.talles.length);
  return pairs.map(([a, b], k) => {
    const s = Math.max(1, Math.round(sessionsTotal * (k === 0 ? 0.6 : 0.4)));
    const ta = m.talles[a], tb = m.talles[b];
    // Als texans, la talla gran guanya: el patró va petit.
    const gran = model === 'TX-26-IND' ? 0.65 : 0.4;
    const cap = Math.round(s * (model === 'VV-26-VRD' ? 0.5 : 0.25));
    const cb = Math.round((s - cap) * gran);
    return { model, nom: m.nom, talles: `${ta}+${tb}`, sessions: s, comprada: { [ta]: s - cap - cb, [tb]: cb, cap }, mostra_petita: s < 10 };
  });
}
function talleMesComprada(ps: T.ParellTalla[]): string | null {
  const tot = new Map<string, number>();
  for (const p of ps) for (const [t, n] of Object.entries(p.comprada)) if (t !== 'cap') tot.set(t, (tot.get(t) ?? 0) + n);
  const millor = [...tot.entries()].sort((a, b) => b[1] - a[1])[0];
  return millor && millor[1] > 0 ? millor[0] : null;
}

export function dubteTallaModel(f: FiltreMock, model: string): T.DubteTallaModel | null {
  const s = sessions(f).mateix_model_diferent_talla.per_model.find((x) => x.model === model);
  if (!s) return { sessions: 0, sessions_model: 40, pct_sessions_model: 0, talla_mes_comprada: null, parells_talla: [], mostra_petita: true };
  const parells = parellsModel(model, s.sessions_dubte);
  return { sessions: s.sessions_dubte, sessions_model: Math.round(s.sessions_dubte / (s.pct_sessions_model || 0.1)), pct_sessions_model: s.pct_sessions_model, talla_mes_comprada: talleMesComprada(parells), parells_talla: parells, mostra_petita: s.sessions_dubte < 10 };
}

// ── Gràfics i xifres dels informes (E.2) ─────────────────────────────────
const SETMANA = ['dl.', 'dt.', 'dc.', 'dj.', 'dv.', 'ds.', 'dg.'];
export function graficsInforme(f: FiltreMock, tipus: T.TipusInforme): { grafics: T.GraficInforme[]; xifres: T.XifraInforme[] } {
  const c = cub(f);
  const prev = cub({ ...f, des: suma(f.des, -dies(f.des, f.fins).length), fins: suma(f.des, -1) });
  const p = sumaProves(c), co = sumaCompres(c), pp = sumaProves(prev), cp = sumaCompres(prev);
  const v = (a: number, b: number) => (b ? arr((a - b) / b, 3) : null);
  const cv = conv(co, p), cvp = conv(cp, pp);
  const dd = dies(f.des, f.fins).filter((d) => d <= avui());
  const vs = tipus === 'diari' ? 'dia anterior' : tipus === 'mensual' ? 'mes anterior' : 'setmana anterior';
  const xifres: T.XifraInforme[] = [
    { etiqueta: 'Proves', valor: p, unitat: 'enter', variacio: v(p, pp), vs },
    { etiqueta: 'Conversió', valor: cv === null ? null : arr(cv), unitat: 'pct', variacio: cv !== null && cvp !== null ? arr(cv - cvp) : null, vs },
    { etiqueta: 'Compres després de provar', valor: co, unitat: 'enter', variacio: v(co, cp), vs },
    { etiqueta: 'Demanda perduda', valor: Math.round(p * 0.02) * 69, unitat: 'eur', variacio: -0.12, vs },
    { etiqueta: 'Temps de resposta', valor: 92, unitat: 'segons', variacio: -0.08, vs },
  ];
  const perCat = new Map<string, [number, number]>();
  for (const x of c) { const k = defModel(x.model)!.categoria; const e = perCat.get(k) ?? [0, 0]; e[0] += x.proves; e[1] += x.compres; perCat.set(k, e); }
  const grafics: T.GraficInforme[] = [];
  if (tipus === 'diari') {
    const hores = ['10', '11', '12', '13', '14', '16', '17', '18', '19', '20'];
    grafics.push({ id: 'sessions_hora', titol: 'Sessions de cabina per hora', tipus: 'barres', unitat: 'enter', eix_x: hores.map((h) => `${h} h`), series: [{ nom: 'Sessions', valors: hores.map((h, i) => Math.round((2 + atzar(`dh${h}${f.fins}`)() * 5) * (i === 2 || i >= 6 ? 1.8 : 1))) }], nota: 'La franja de 15 h és tancada.' });
  } else {
    grafics.push({
      id: 'proves_compres_dia', titol: 'Proves i compres per dia', tipus: 'linia', unitat: 'enter',
      eix_x: dd.map((d) => (dd.length <= 7 ? SETMANA[(dataLocal(d).getDay() + 6) % 7] : d.slice(8, 10))),
      series: [{ nom: 'Proves', valors: dd.map((d) => sumaProves(c.filter((x) => x.data === d))) }, { nom: 'Compres', valors: dd.map((d) => sumaCompres(c.filter((x) => x.data === d))) }],
    });
    grafics.push({ id: 'conversio_categoria', titol: 'Conversió per categoria', tipus: 'barres', unitat: 'pct', eix_x: [...perCat.keys()], series: [{ nom: 'Conversió', valors: [...perCat.values()].map(([a, b]) => (a ? arr(b / a) : null)) }] });
    grafics.push({ id: 'peces_sessio', titol: 'Sessions segons les peces que s’hi proven', tipus: 'barres_apilades', unitat: 'enter', eix_x: ['1', '2', '3', '4', '5+'], series: [{ nom: 'Amb compra', valors: [22, 28, 23, 15, 11].map((x) => Math.round(x * (p / 500))) }, { nom: 'Sense compra', valors: [56, 45, 26, 13, 8].map((x) => Math.round(x * (p / 500))) }], nota: 'Com més peces s’emporten a la cabina, més sovint compren.' });
    grafics.push({ id: 'motius', titol: 'Per què no se l’emporten', tipus: 'donut', unitat: 'enter', eix_x: ['Talla', 'Tall o patró', 'Preu', 'Color', 'Qualitat'], series: [{ nom: 'Respostes', valors: [24, 21, 20, 8, 5] }] });
  }
  if (tipus === 'mensual' || tipus === 'pilot' || tipus === 'mango') {
    grafics.splice(1, 0, { id: 'conversio_setmanal', titol: 'Conversió per setmana, amb i sense origen', tipus: 'linia', unitat: 'pct', eix_x: ['S42', 'S43', 'S44', 'S45'], series: [{ nom: 'Amb origen', valors: [0.36, 0.38, 0.35, 0.39] }, { nom: 'Sense origen', valors: [0.31, 0.32, 0.33, 0.31] }], nota: 'Dies sortejats: la prova d’origen continua fins al 29 de novembre.' });
  }
  return { grafics, xifres: tipus === 'diari' ? xifres.slice(0, 3) : xifres };
}

// ── Informes lliurats i programació ──────────────────────────────────────
export const lliuratsMock: (T.InformeLliurat & { programacio_id: number | null })[] = [];
let seguentLliurat = 1;
export function afegeixLliurat(tipus: T.TipusInforme, botiga: string | null, des: string, fins: string, generat: string, programacio_id: number | null, enviat_a: string[]): T.InformeLliurat & { programacio_id: number | null } {
  const l = { id: seguentLliurat++, tipus, botiga_id: botiga, des, fins, generat, estat_enviament: (enviat_a.length ? 'enviat' : 'no_enviat') as T.EstatEnviament, enviat_a, programacio_id };
  lliuratsMock.unshift(l);
  return l;
}
(() => {
  const avuiIso = avui();
  const dl = dataLocal(avuiIso); dl.setDate(dl.getDate() - ((dl.getDay() + 6) % 7));
  const dilluns = isoData(dl);
  const entrades: [T.TipusInforme, string | null, string, string, string, number | null, string[]][] = [];
  // Mensual d'octubre i setmanals de les 4 setmanes anteriors
  entrades.push(['mensual', null, '2026-10-01', '2026-10-31', '2026-11-01T08:00:00+01:00', 3, ['direccio@marca.cat', 'producte@marca.cat']]);
  for (let s = 4; s >= 1; s--) {
    const d = suma(dilluns, -7 * s);
    entrades.push(['setmanal', null, d, suma(d, 6), `${suma(d, 7)}T08:00:00+01:00`, 2, ['producte@marca.cat', 'botiga.gracia@marca.cat']]);
  }
  for (let i = 9; i >= 1; i--) {
    const d = suma(avuiIso, -i);
    if (dataLocal(d).getDay() === 1) continue; // dilluns tancat
    entrades.push(['diari', 'BCN-01', d, d, `${suma(d, 1)}T08:00:00+01:00`, 1, ['botiga.gracia@marca.cat']]);
  }
  entrades.push(['pilot', null, '2026-10-19', suma(avuiIso, -1), `${suma(avuiIso, -1)}T17:42:00+01:00`, null, []]);
  entrades.sort((a, b) => a[4].localeCompare(b[4]));
  for (const e of entrades) afegeixLliurat(...e);
  const l = lliuratsMock.find((x) => x.tipus === 'diari');
  if (l) { l.estat_enviament = 'error'; }
})();

let seguentProg = 5;
export const programacionsMock: Omit<T.Programacio, 'propera'>[] = [
  { id: 1, botiga_id: 'BCN-01', tipus: 'diari', actiu: true, dia_setmana: null, dia_mes: null, data: null, hora: '08:00', destinataris: ['botiga.gracia@marca.cat'] },
  { id: 2, botiga_id: null, tipus: 'setmanal', actiu: true, dia_setmana: 0, dia_mes: null, data: null, hora: '08:00', destinataris: ['producte@marca.cat', 'botiga.gracia@marca.cat'] },
  { id: 3, botiga_id: null, tipus: 'mensual', actiu: true, dia_setmana: null, dia_mes: 1, data: null, hora: '08:00', destinataris: ['direccio@marca.cat', 'producte@marca.cat'] },
  { id: 4, botiga_id: null, tipus: 'temporada', actiu: true, dia_setmana: null, dia_mes: null, data: '2027-02-15', hora: '09:00', destinataris: ['disseny@marca.cat', 'producte@marca.cat'] },
];
export const ambPropera = (p: Omit<T.Programacio, 'propera'>): T.Programacio => ({ ...p, propera: properaExecucio(p)?.toISOString() ?? null });
export function creaProgramacio(c: T.NovaProgramacio): T.Programacio {
  const p = { ...c, id: seguentProg++ };
  programacionsMock.push(p);
  return ambPropera(p);
}

/** PDF mínim i vàlid (una pàgina amb text), perquè «Descarrega PDF» funcioni a la demo. */
export function pdfDemo(titol: string): string {
  const net = titol.replace(/[()\\]/g, '').normalize('NFD').replace(/[^\x20-\x7e]/g, '');
  const text = `BT /F1 20 Tf 56 770 Td (${net}) Tj 0 -28 Td /F1 11 Tf (Demo de Hebra: a la plataforma real, aquest PDF el genera el servidor amb els grafics.) Tj ET`;
  const objs = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  let out = '%PDF-1.4\n';
  const offs: number[] = [];
  objs.forEach((o, i) => { offs.push(out.length); out += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n${offs.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}`;
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return out;
}

// ── Fitxa NFC (A) ────────────────────────────────────────────────────────
export const CONFIG_GENERAL: T.ConfigFitxa = {
  seccions: { ordre: ['talles', 'composicio', 'origen', 'cura', 'combina', 'faq'], visibles: { talles: true, composicio: true, origen: true, cura: true, combina: true, faq: true } },
  accions: { demana_talla: true, demana_assistencia: true, per_que_no: true, mostra_estoc: 'disponibilitat' },
  idiomes: ['ca', 'es', 'fr', 'en'],
  textos: {
    benvinguda: { ca: 'Gràcies per provar-te una peça Hebra. Aquí tens tot el que cal saber.', es: 'Gracias por probarte una prenda Hebra. Aquí tienes todo lo que necesitas saber.' },
    peu: { ca: 'Fet amb cura a la Mediterrània.', es: 'Hecho con cuidado en el Mediterráneo.' },
  },
  'aparença': { color_principal: '#214F46', logo_data_url: null, nom_marca: 'Hebra' },
  motius: ['talla', 'preu', 'tall', 'qualitat', 'color', 'nomes_mirava'],
};
export const configBotigues: Record<string, T.ConfigFitxaParcial> = {
  'MAD-01': { idiomes: ['es', 'en', 'ca'], accions: { mostra_estoc: 'unitats' } },
};
export function configEfectiva(botiga: string | null): T.ConfigFitxa {
  const g = structuredClone(CONFIG_GENERAL);
  const b = botiga ? configBotigues[botiga] : null;
  if (!b) return g;
  for (const k of Object.keys(b) as (keyof T.ConfigFitxa)[]) {
    const v = b[k];
    if (v === undefined) continue;
    if (Array.isArray(v)) (g as unknown as Record<string, unknown>)[k] = v;
    else Object.assign(g[k] as object, v);
  }
  return g;
}

export const continguts: Record<string, Record<string, T.ContingutModel>> = {
  'CL-24-NAT': {
    ca: { nom: 'Camisa de lli', descripcio: 'Camisa de lli rentat, ampla i fresca, amb coll clàssic i botons de nacre.', ajust: 'Tall ample. Si dubtes entre dues talles, tria la petita.', cura: ['Rentar a 30 °C', 'No assecar a màquina', 'Planxar humida'], guia_talles: 'Pit: S 104 cm · M 110 cm · L 116 cm', faq: [{ q: 'Arruga gaire?', a: 'Sí, és lli: l’arruga forma part de la peça.' }], combina: ['TX-26-IND', 'PL-26-TER'] },
    es: { nom: 'Camisa de lino', descripcio: 'Camisa de lino lavado, amplia y fresca, con cuello clásico y botones de nácar.', ajust: 'Corte amplio. Si dudas entre dos tallas, elige la pequeña.', cura: ['Lavar a 30 °C', 'No usar secadora'], combina: ['TX-26-IND'] },
  },
  'TX-26-IND': { ca: { nom: 'Texans rectes', descripcio: 'Texà de cotó orgànic, tall recte i cintura mitjana.', ajust: 'Van una mica justos: molts clients agafen una talla més.', cura: ['Rentar del revés a 30 °C'], combina: ['CL-24-NAT', 'JM-24-GRF'] } },
  'JM-24-GRF': { ca: { nom: 'Jersei de merino', descripcio: 'Jersei de punt fi de merino, càlid i lleuger.', cura: ['Rentar a mà amb aigua freda', 'Assecar en pla'] } },
};
export const ORIGEN_FITXA = (model: string): Record<string, unknown> | null => {
  const o = ORIGENS[model];
  const m = defModel(model);
  if (!m) return null;
  return { nom: m.nom, descripcio: `${m.nom} de la col·lecció d’hivern.`, cura: ['Rentar a 30 °C'], etapes: o?.etapes ?? [], composicio: o?.composicio ?? [] };
};
export function modelsFitxa(): T.ModelFitxa[] {
  return MODELS.map((m) => ({ model: m.model, nom: m.nom, categoria: m.categoria, idiomes_amb_contingut: Object.keys(continguts[m.model] ?? {}), te_origen: !!ORIGENS[m.model] }));
}

const COLOR = /^#[0-9A-Fa-f]{6}$/;
const SECCIONS: T.SeccioFitxa[] = ['talles', 'composicio', 'origen', 'cura', 'combina', 'faq'];
const MOTIUS: T.MotiuFitxa[] = ['talla', 'preu', 'tall', 'qualitat', 'color', 'nomes_mirava', 'altre'];
export function validaConfig(c: T.ConfigFitxaParcial): string | null {
  const ap = c['aparença'];
  if (ap?.color_principal !== undefined && !COLOR.test(ap.color_principal)) return 'El color ha de ser del tipus #RRGGBB.';
  if (ap?.logo_data_url) {
    if (!/^data:image\/(png|svg\+xml);base64,/.test(ap.logo_data_url)) return 'El logo ha de ser una imatge PNG o SVG.';
    if (ap.logo_data_url.length * 0.75 > 100 * 1024) return 'El logo no pot passar de 100 KB.';
  }
  if (c.seccions?.ordre && c.seccions.ordre.some((s) => !SECCIONS.includes(s))) return 'Hi ha una secció desconeguda.';
  if (c.motius && c.motius.some((m) => !MOTIUS.includes(m))) return 'Hi ha un motiu desconegut.';
  if (c.idiomes && !c.idiomes.length) return 'La fitxa ha d’oferir com a mínim un idioma.';
  return null;
}

// ── Integracions (F) ─────────────────────────────────────────────────────
let seguentIntegracio = 3;
export const integracionsMock: (T.Integracio & { registre: T.RegistreSync[] })[] = [
  {
    id: 1, botiga_id: 'BCN-01', proveidor: 'shopify', config: { domini: 'hebra-gracia.myshopify.com', ubicacio_id: '7712', ubicacio_nom: 'Gràcia (botiga física)', incloure_en_linia: false, opcio_talla: 'Talla', opcio_color: 'Color' },
    te_secret: true, actiu: true, abast: ['cataleg', 'vendes', 'estoc'], interval_min: 60, darrera_sync: fa(23), estat: 'ok', missatge: '31 línies de venda, 2 devolucions, 214 nivells d’estoc.',
    registre: Array.from({ length: 6 }, (_, i) => ({ inici: fa(23 + 60 * i), fi: fa(22.6 + 60 * i), estat: 'ok', resum: { cataleg: i === 5 ? 186 : 0, linies_venda: 31 - i * 3, devolucions: i % 3 === 0 ? 2 : 0, estoc: 214 }, error: null })),
  },
  {
    id: 2, botiga_id: 'GIR-01', proveidor: 'csv_url', config: { url_vendes: 'https://tpv.example.cat/export/vendes.csv', url_estoc: 'https://tpv.example.cat/export/estoc.csv', url_cataleg: '' },
    te_secret: false, actiu: true, abast: ['vendes', 'estoc'], interval_min: 120, darrera_sync: fa(95), estat: 'error', missatge: 'La URL de vendes ha respost 404 (no trobat). Comprova que el TPV encara exporti el fitxer.',
    registre: [
      { inici: fa(95), fi: fa(94.8), estat: 'error', resum: null, error: 'La URL de vendes ha respost 404 (no trobat).' },
      { inici: fa(215), fi: fa(214.5), estat: 'ok', resum: { linies_venda: 12, devolucions: 0, estoc: 88 }, error: null },
    ],
  },
];
export const publica = ({ registre: _r, ...i }: T.Integracio & { registre: T.RegistreSync[] }): T.Integracio => i;

export function provaIntegracio(c: { proveidor: T.Proveidor; config: Record<string, unknown>; secret?: string | null; id?: number }): { estat: number; cos: unknown } {
  const desat = c.id ? integracionsMock.find((x) => x.id === c.id) : undefined;
  const teSecret = !!c.secret || !!desat?.te_secret;
  if (c.proveidor === 'shopify') {
    const d = String(c.config.domini ?? '');
    if (!/^[a-z0-9-]+\.myshopify\.com$/.test(d)) return { estat: 400, cos: { detail: 'El domini ha de ser del tipus nom-botiga.myshopify.com.' } };
    if (!teSecret) return { estat: 400, cos: { detail: 'Falta el testimoni d’accés (comença per shpat_).' } };
    if (c.secret && !c.secret.startsWith('shpat_')) return { estat: 400, cos: { detail: 'Shopify ha rebutjat el testimoni: ha de començar per shpat_ i tenir permisos de lectura.' } };
    return { estat: 200, cos: { ok: true, detail: undefined, detall: { botiga: 'Hebra · Gràcia', moneda: 'EUR', ubicacions: [{ id: '7712', nom: 'Gràcia (botiga física)' }, { id: '7713', nom: 'Magatzem central' }, { id: '7714', nom: 'Botiga en línia' }] } } };
  }
  if (c.proveidor === 'square') {
    if (!teSecret) return { estat: 400, cos: { detail: 'Falta el testimoni d’accés de Square.' } };
    return { estat: 200, cos: { ok: true, detall: { botiga: 'Hebra Madrid', ubicacions: [{ id: 'L8XK2', nom: 'Malasaña' }] } } };
  }
  const urls = ['url_vendes', 'url_estoc', 'url_cataleg'].map((k) => String(c.config[k] ?? '')).filter(Boolean);
  if (!urls.length) return { estat: 400, cos: { detail: 'Escriu com a mínim una URL.' } };
  if (urls.some((u) => !u.startsWith('https://'))) return { estat: 400, cos: { detail: 'Les URL han de començar per https://.' } };
  return { estat: 200, cos: { ok: true, detall: { fitxers: urls.map((u) => ({ url: u, files: 40 + Math.floor(Math.random() * 60), columnes: 'data_hora;botiga;gtin;quantitat' })) } } };
}

export function creaIntegracio(c: T.NovaIntegracio): T.Integracio {
  const i = { id: seguentIntegracio++, botiga_id: c.botiga_id, proveidor: c.proveidor, config: c.config, te_secret: !!c.secret, actiu: true, abast: c.abast, interval_min: Math.max(15, c.interval_min || 60), darrera_sync: null, estat: 'mai' as const, missatge: null, registre: [] };
  integracionsMock.push(i);
  return publica(i);
}

export function sincronitza(id: number): { estat: number; cos: unknown } {
  const i = integracionsMock.find((x) => x.id === id);
  if (!i) return { estat: 404, cos: { detail: 'Aquesta connexió no existeix.' } };
  const inici = fa(0.1);
  if (i.proveidor === 'csv_url' && String(i.config.url_vendes ?? '').includes('example')) {
    i.estat = 'error'; i.darrera_sync = fa(0); i.missatge = 'La URL de vendes ha respost 404 (no trobat).';
    i.registre.unshift({ inici, fi: fa(0), estat: 'error', resum: null, error: i.missatge });
    return { estat: 400, cos: { detail: i.missatge } };
  }
  const resum: T.ResumSync = { cataleg: i.abast.includes('cataleg') ? 4 : 0, linies_venda: i.abast.includes('vendes') ? 7 : 0, devolucions: i.abast.includes('vendes') ? 1 : 0, estoc: i.abast.includes('estoc') ? 214 : 0 };
  i.estat = 'ok'; i.darrera_sync = fa(0); i.missatge = `${resum.linies_venda} línies de venda, ${resum.devolucions} devolució, ${resum.estoc} nivells d’estoc.`;
  i.registre.unshift({ inici, fi: fa(0), estat: 'ok', resum, error: null });
  return { estat: 200, cos: { resum } };
}

// Peticions inicials amb els camps nous
for (const p of estat.peticions) {
  p.tipus = 'talla';
  p.altres_botigues = p.disponible ? [] : altresBotigues(p.model, p.talla);
}
estat.peticions.splice(1, 0, { id: 38, model: 'VV-26-VRD', nom: 'Vestit de viscosa', color: 'Verd', talla: '', cabina: 'BCN-01-C2', hora_peticio: fa(0.6), estat: 'pendent', disponible: true, segons_espera: 36, tipus: 'assistencia', altres_botigues: [] });
