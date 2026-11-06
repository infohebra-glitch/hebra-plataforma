/**
 * Dades del mode demostració. Partim dels exemples de docs/API.md i els fem
 * créixer: 3 botigues, 7 models, una sèrie diària per a qualsevol període i
 * una prova d'origen en curs. Tot surt d'un «cub» dia × botiga × model calculat
 * amb atzar determinista, perquè totals, sèries i detalls quadrin entre ells.
 */
import type * as T from '../api/types';
import { dataLocal, isoData } from '../lib/format';
import { atzar, provaDuesProporcions } from './estadistica';

export const BOTIGUES: T.Botiga[] = [
  { id: 'BCN-01', nom: 'Barcelona · Gràcia', nivell: 'cabina' },
  { id: 'GIR-01', nom: 'Girona · Barri Vell', nivell: 'basic' },
  { id: 'MAD-01', nom: 'Madrid · Malasaña', nivell: 'cabina' },
];
const PES_BOTIGA: Record<string, number> = { 'BCN-01': 38, 'GIR-01': 19, 'MAD-01': 27 };

interface DefModel {
  model: string; nom: string; categoria: string; color: string; preu: number;
  pes: number; conv: number; talles: string[]; pesTalla: number[]; convTalla?: Record<string, number>;
  estocTalla: number[]; motius: Partial<Record<T.Motiu, number>>; provatAmb: string[];
}

const LLETRES = ['XS', 'S', 'M', 'L', 'XL'];
const NUMS = ['36', '38', '40', '42', '44'];

export const MODELS: DefModel[] = [
  { model: 'CL-24-NAT', nom: 'Camisa de lli', categoria: 'part de dalt', color: 'Natural', preu: 69, pes: 0.22, conv: 0.42, talles: LLETRES, pesTalla: [0.08, 0.24, 0.33, 0.24, 0.11], estocTalla: [3, 4, 1, 0, 2], motius: { talla: 8, preu: 4, tall: 3, color: 2, qualitat: 2, altre: 1 }, provatAmb: ['TX-26-IND', 'PL-26-TER', 'FA-26-BLA'] },
  { model: 'VV-26-VRD', nom: 'Vestit de viscosa', categoria: 'vestit', color: 'Verd', preu: 79, pes: 0.2, conv: 0.14, talles: LLETRES.slice(0, 4), pesTalla: [0.15, 0.32, 0.33, 0.2], estocTalla: [4, 5, 3, 2], motius: { tall: 9, preu: 6, talla: 4, qualitat: 3, color: 1 }, provatAmb: ['JM-24-GRF', 'FA-26-BLA'] },
  { model: 'TX-26-IND', nom: 'Texans rectes', categoria: 'part de baix', color: 'Índigo', preu: 59, pes: 0.17, conv: 0.3, talles: NUMS, pesTalla: [0.12, 0.27, 0.3, 0.2, 0.11], convTalla: { '38': 0.38 }, estocTalla: [2, 6, 4, 3, 1], motius: { talla: 7, tall: 4, preu: 2, altre: 1 }, provatAmb: ['CL-24-NAT', 'JM-24-GRF', 'SB-25-CRU'] },
  { model: 'JM-24-GRF', nom: 'Jersei de merino', categoria: 'part de dalt', color: 'Grafit', preu: 89, pes: 0.14, conv: 0.36, talles: LLETRES, pesTalla: [0.06, 0.2, 0.45, 0.21, 0.08], estocTalla: [2, 3, 3, 4, 3], motius: { preu: 5, talla: 2, color: 1 }, provatAmb: ['TX-26-IND', 'PL-26-TER'] },
  { model: 'SB-25-CRU', nom: 'Sobrecamisa de cotó', categoria: 'part de dalt', color: 'Cru', preu: 75, pes: 0.1, conv: 0.33, talles: LLETRES, pesTalla: [0.05, 0.2, 0.35, 0.28, 0.12], estocTalla: [1, 3, 4, 3, 2], motius: { tall: 2, preu: 2, talla: 1 }, provatAmb: ['TX-26-IND'] },
  { model: 'PL-26-TER', nom: 'Pantaló de lli', categoria: 'part de baix', color: 'Terra', preu: 65, pes: 0.1, conv: 0.24, talles: NUMS, pesTalla: [0.15, 0.3, 0.3, 0.17, 0.08], estocTalla: [5, 7, 6, 5, 4], motius: { tall: 3, color: 2, talla: 2 }, provatAmb: ['CL-24-NAT', 'JM-24-GRF'] },
  { model: 'FA-26-BLA', nom: 'Faldilla midi', categoria: 'part de baix', color: 'Blau nit', preu: 55, pes: 0.07, conv: 0.38, talles: LLETRES.slice(0, 4), pesTalla: [0.18, 0.34, 0.3, 0.18], estocTalla: [2, 2, 3, 1], motius: { color: 2, preu: 1 }, provatAmb: ['CL-24-NAT', 'VV-26-VRD'] },
];
export const defModel = (m: string) => MODELS.find((x) => x.model === m);

export const ORIGENS: Record<string, T.Origen> = {
  'CL-24-NAT': {
    etapes: [
      { etapa: 'Cultiu del lli', pais: 'França', regio: 'Normandia' },
      { etapa: 'Filatura', pais: 'Itàlia', regio: 'Biella' },
      { etapa: 'Teixit', pais: 'Espanya', regio: 'Bages' },
      { etapa: 'Confecció', pais: 'Portugal', regio: 'Barcelos' },
    ],
    composicio: [{ material: 'Lli', pct: 1, pais: 'França' }],
  },
  'JM-24-GRF': {
    etapes: [
      { etapa: 'Llana', pais: 'Uruguai', regio: 'Durazno' },
      { etapa: 'Filatura', pais: 'Itàlia', regio: 'Biella' },
      { etapa: 'Tricotat', pais: 'Espanya', regio: 'Anoia' },
    ],
    composicio: [{ material: 'Llana merino', pct: 0.95, pais: 'Uruguai' }, { material: 'Poliamida', pct: 0.05, pais: 'Itàlia' }],
  },
  'TX-26-IND': {
    etapes: [
      { etapa: 'Cotó', pais: 'Turquia', regio: 'Esmirna' },
      { etapa: 'Teixit i tint', pais: 'Turquia', regio: 'Esmirna' },
      { etapa: 'Confecció', pais: 'Marroc', regio: 'Tànger' },
    ],
    composicio: [{ material: 'Cotó orgànic', pct: 0.98, pais: 'Turquia' }, { material: 'Elastà', pct: 0.02, pais: 'Turquia' }],
  },
};

// ── Període i cub ─────────────────────────────────────────────────────────

const suma = (iso: string, n: number) => { const d = dataLocal(iso); d.setDate(d.getDate() + n); return isoData(d); };
export const avui = () => isoData(new Date());
export function dies(des: string, fins: string): string[] {
  const r: string[] = [];
  for (let d = des; d <= fins && r.length < 400; d = suma(d, 1)) r.push(d);
  return r;
}
const diaSetmana = (iso: string) => (dataLocal(iso).getDay() + 6) % 7; // 0 = dl.

export interface FiltreMock { botigues: string[]; des: string; fins: string }

export function filtre(q: URLSearchParams): FiltreMock {
  const fins = q.get('fins') || avui();
  const des = q.get('des') || suma(fins, -6);
  const b = q.get('botiga');
  return { botigues: b ? [b] : BOTIGUES.map((x) => x.id), des, fins };
}

export function anterior(f: FiltreMock): FiltreMock {
  const n = dies(f.des, f.fins).length;
  return { ...f, des: suma(f.des, -n), fins: suma(f.des, -1) };
}

/** Grup de la prova d'origen: sorteig per dia (amb = la fitxa ensenya l'origen). */
export const INICI_ORIGEN = '2026-10-19';
export const FI_ORIGEN = '2026-11-29';
export function grupDia(data: string): T.GrupOrigen | null {
  if (data < INICI_ORIGEN || data > FI_ORIGEN) return null;
  return atzar(`grup${data}`)() < 0.45 ? 'amb' : 'sense';
}

const FACTOR_DIA = [0.8, 0.85, 0.9, 1.0, 1.2, 1.7, 0];

export interface Cella { data: string; botiga: string; model: string; talla: string; proves: number; compres: number; grup: T.GrupOrigen | null }

const memo = new Map<string, Cella[]>();

export function cub(f: FiltreMock): Cella[] {
  const clau = `${f.botigues.join(',')}|${f.des}|${f.fins}`;
  const desat = memo.get(clau);
  if (desat) return desat;
  const r: Cella[] = [];
  for (const data of dies(f.des, f.fins)) {
    if (data > avui()) continue; // el futur encara no té dades
    const grup = grupDia(data);
    for (const b of f.botigues) {
      const fd = FACTOR_DIA[diaSetmana(data)] * PES_BOTIGA[b];
      for (const m of MODELS) {
        m.talles.forEach((talla, i) => {
          const rnd = atzar(`${data}${b}${m.model}${talla}`);
          const esperat = fd * m.pes * m.pesTalla[i] * (0.75 + rnd() * 0.5);
          const proves = Math.round(esperat + (rnd() - 0.5));
          const efecte = grup === 'amb' ? 1.14 : grup === 'sense' ? 0.95 : 1;
          const conv = Math.min(0.95, m.conv * (m.convTalla?.[talla] ?? 1) * efecte);
          let compres = 0;
          for (let k = 0; k < proves; k++) if (rnd() < conv) compres++;
          if (proves > 0) r.push({ data, botiga: b, model: m.model, talla, proves, compres, grup });
        });
      }
    }
  }
  memo.set(clau, r);
  return r;
}

export const sumaProves = (c: Cella[]) => c.reduce((s, x) => s + x.proves, 0);
export const sumaCompres = (c: Cella[]) => c.reduce((s, x) => s + x.compres, 0);
export const conv = (compres: number, proves: number): number | null => (proves ? compres / proves : null);
export const arr = (x: number, d = 3) => Number(x.toFixed(d));

export function experimentOrigen(f: FiltreMock, model?: string): T.Experiment {
  const fins = f.fins < FI_ORIGEN ? f.fins : FI_ORIGEN;
  const c = cub({ botigues: f.botigues, des: INICI_ORIGEN, fins }).filter((x) => !model || x.model === model);
  const amb = c.filter((x) => x.grup === 'amb'), sense = c.filter((x) => x.grup === 'sense');
  const pa = sumaProves(amb), ca = sumaCompres(amb), ps = sumaProves(sense), cs = sumaCompres(sense);
  const prova = provaDuesProporcions(ca, pa, cs, ps);
  const minimes = 30;
  const suficient = pa >= minimes && ps >= minimes;
  const restantsDies = Math.max(0, dies(avui(), FI_ORIGEN).length - 1);
  const setmanes = Math.ceil(restantsDies / 7);
  const pTxt = prova ? prova.p_valor.toFixed(2).replace('.', ',') : '—';
  let conclusio: string;
  if (!suficient) conclusio = `Mostra petita: cal un mínim de ${minimes} proves per grup abans de mirar-ne el resultat.`;
  else if (prova && prova.p_valor < 0.05) conclusio = `Els dies amb origen visible es converteix més (p = ${pTxt}). Encara falten ${setmanes} setmanes per tancar la prova.`;
  else conclusio = `Encara no hi ha diferència demostrable (p = ${pTxt}). Falten ${setmanes} setmanes.`;
  return {
    id: 'origen-2026-11', variable: 'origen', unitat: 'dia', inici: INICI_ORIGEN, fi: FI_ORIGEN, estat: 'actiu',
    hipotesi: 'Ensenyar a la fitxa NFC d’on ve la peça (etapes i països) fa que se la quedin més sovint.',
    grups: { amb: { proves: pa, compres: ca, conversio: conv(ca, pa) }, sense: { proves: ps, compres: cs, conversio: conv(cs, ps) } },
    diferencia: prova ? arr(prova.diferencia) : null,
    ic95: prova ? [arr(prova.ic95[0]), arr(prova.ic95[1])] : null,
    p_valor: prova ? arr(prova.p_valor, 3) : null,
    proves_minimes: minimes, mostra_suficient: suficient,
    proves_necessaries: prova ? prova.proves_necessaries : null,
    setmanes_restants: setmanes, conclusio,
  };
}

export const EXPERIMENT_ACABAT: T.Experiment = (() => {
  const prova = provaDuesProporcions(212, 488, 171, 502)!;
  return {
    id: 'peticio-talla-2026-09', variable: 'peticio_talla', unitat: 'dia', inici: '2026-09-07', fi: '2026-10-11', estat: 'acabat',
    hipotesi: 'Deixar demanar una altra talla des de la fitxa NFC, sense sortir de la cabina, fa vendre més.',
    grups: { amb: { proves: 488, compres: 212, conversio: arr(212 / 488) }, sense: { proves: 502, compres: 171, conversio: arr(171 / 502) } },
    diferencia: arr(prova.diferencia), ic95: [arr(prova.ic95[0]), arr(prova.ic95[1])], p_valor: arr(prova.p_valor, 3),
    proves_minimes: 30, mostra_suficient: true, proves_necessaries: prova.proves_necessaries, setmanes_restants: 0,
    conclusio: 'Els dies amb petició de talla a la fitxa es van convertir 9 punts més. És poc probable que sigui casualitat: s’ha deixat activat a totes les botigues.',
  };
})();

// ── Estat mutable (operació) ─────────────────────────────────────────────

const ara = () => new Date();
const fa = (min: number) => new Date(ara().getTime() - min * 60000).toISOString();

export const estat = {
  peticions: [
    { id: 41, model: 'JM-24-GRF', nom: 'Jersei de merino', color: 'Grafit', talla: 'M', cabina: 'BCN-01-C2', hora_peticio: fa(1.2), estat: 'pendent', disponible: true, segons_espera: 72 },
    { id: 40, model: 'CL-24-NAT', nom: 'Camisa de lli', color: 'Natural', talla: 'L', cabina: 'BCN-01-C1', hora_peticio: fa(3), estat: 'pendent', disponible: false, segons_espera: 180 },
    { id: 39, model: 'TX-26-IND', nom: 'Texans rectes', color: 'Índigo', talla: '40', cabina: 'BCN-01-C3', hora_peticio: fa(4), estat: 'en_cami', disponible: true, segons_espera: 240 },
  ] as T.Peticio[],
  abandonades: [
    { id: 7, epc: '3034F8A1C2000000000017A2', model: 'VV-26-VRD', nom: 'Vestit de viscosa', talla: 'S', cabina: 'BCN-01-C2', detectada: fa(38), resolta: false },
    { id: 6, epc: '3034F8A1C2000000000016B9', model: 'PL-26-TER', nom: 'Pantaló de lli', talla: '40', cabina: 'BCN-01-C1', detectada: fa(52), resolta: false },
  ] as T.Abandonada[],
  decisions: [
    { id: 4, botiga_id: null, creada: '2026-10-27T10:12:00+01:00', titol: 'Revisar el patró dels texans en 38', descripcio: 'La 38 es prova molt i es ven a 1 de cada 8 proves. Demanar al taller una mostra amb més tir de cintura.', insight: 6, model: 'TX-26-IND', responsable: 'Producte · Marta', data_limit: '2026-11-14', estat: 'acceptada', experiment_id: null, resultat: null },
    { id: 3, botiga_id: 'BCN-01', creada: '2026-10-20T09:00:00+02:00', titol: 'Reposar la camisa de lli en L', descripcio: '5 peticions en una setmana sense estoc a la botiga.', insight: 7, model: 'CL-24-NAT', responsable: 'Botiga Gràcia · Jordi', data_limit: '2026-10-24', estat: 'feta', experiment_id: null, resultat: 'Reposades 6 unitats el 22/10; se n’han venut 4 en 10 dies.' },
    { id: 2, botiga_id: null, creada: '2026-10-13T16:30:00+02:00', titol: 'Provar l’origen a la fitxa NFC', descripcio: 'Prova A/B per dies durant 6 setmanes a les tres botigues.', insight: 17, model: null, responsable: 'Màrqueting · Núria', data_limit: '2026-11-29', estat: 'acceptada', experiment_id: 'origen-2026-11', resultat: null },
    { id: 1, botiga_id: null, creada: '2026-10-06T11:00:00+02:00', titol: 'Baixar el preu del vestit de viscosa', descripcio: 'Descartat: els motius apunten al tall, no al preu.', insight: 3, model: 'VV-26-VRD', responsable: 'Direcció', data_limit: null, estat: 'descartada', experiment_id: null, resultat: null },
  ] as T.Decisio[],
  parametres: { marge_peca: '40', quota_mensual: '350', pvp_mitja: '69', n_molt_provat: '10', dies_estoc_parat: '21', setmanes_cobertura: '8', minuts_abandonada: '30', senyals_perdua: '0' } as Record<string, string>,
  seguentPeticio: 42,
  seguentAbandonada: 8,
  seguentDecisio: 5,
};

/** Una petició nova, com si un client la fes des de la fitxa NFC. */
export function novaPeticio(): T.Peticio {
  const r = atzar(`p${estat.seguentPeticio}`);
  const m = MODELS[Math.floor(r() * MODELS.length)];
  const talla = m.talles[Math.floor(r() * m.talles.length)];
  const p: T.Peticio = {
    id: estat.seguentPeticio++, model: m.model, nom: m.nom, color: m.color, talla,
    cabina: `BCN-01-C${1 + Math.floor(r() * 3)}`, hora_peticio: new Date().toISOString(), estat: 'pendent',
    disponible: r() > 0.25, segons_espera: 0,
  };
  estat.peticions.unshift(p);
  return p;
}
