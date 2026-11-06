/**
 * Servidor fals per al mode demostració: respon les mateixes rutes que
 * /api/v2 (docs/API.md) amb dades calculades a dades.ts.
 */
import type * as T from '../api/types';
import { atzar } from './estadistica';
import {
  BOTIGUES, EXPERIMENT_ACABAT, MODELS, ORIGENS, anterior, arr, conv, cub, defModel, dies, estat, experimentOrigen,
  filtre, grupDia, sumaCompres, sumaProves, type Cella, type FiltreMock,
} from './dades';
import { isoData, dataLocal } from '../lib/format';

type Cos = unknown;
interface Resposta { estat: number; cos: Cos }
const ok = (cos: Cos): Resposta => ({ estat: 200, cos });
const error = (estat: number, detail: string): Resposta => ({ estat, cos: { detail } });

// ── Sessió ───────────────────────────────────────────────────────────────
const CLAU_SESSIO = 'hebra-mock-usuari';
const USUARI_MARCA: T.Usuari = { id: 1, nom: 'Laia Puig', correu: 'laia@marca.cat', rol: 'admin', botiga_id: null };
const USUARI_BOTIGA: T.Usuari = { id: 2, nom: 'Jordi Vila', correu: 'botiga@marca.cat', rol: 'botiga', botiga_id: 'BCN-01' };

function usuariActual(): T.Usuari | null {
  let v: string | null = null;
  try { v = sessionStorage.getItem(CLAU_SESSIO); } catch { /* sense emmagatzematge */ }
  if (v === 'fora') return null;
  if (v === 'botiga') return USUARI_BOTIGA;
  return USUARI_MARCA; // per defecte, la demostració comença amb la sessió oberta
}
function desaSessio(v: 'marca' | 'botiga' | 'fora') { try { sessionStorage.setItem(CLAU_SESSIO, v); } catch { /* res */ } }

// ── Agregats ─────────────────────────────────────────────────────────────
const nSetmanes = (f: FiltreMock) => Math.max(1, dies(f.des, f.fins).length / 7);
const escala = (f: FiltreMock, perSetmana: number) => Math.round(perSetmana * nSetmanes(f) * (f.botigues.length / BOTIGUES.length));

function perModel(c: Cella[]) {
  const r = new Map<string, Cella[]>();
  for (const x of c) { const l = r.get(x.model) ?? []; l.push(x); r.set(x.model, l); }
  return r;
}

function models(f: FiltreMock): T.ModelResum[] {
  const c = cub(f);
  const pm = perModel(c);
  const mitjana = conv(sumaCompres(c), sumaProves(c)) ?? 0;
  const llindar = Math.round(Number(estat.parametres.n_molt_provat) * nSetmanes(f) * (f.botigues.length / BOTIGUES.length));
  const files = MODELS.map((m) => {
    const cm = pm.get(m.model) ?? [];
    const proves = sumaProves(cm), compres = sumaCompres(cm);
    const cat = c.filter((x) => defModel(x.model)?.categoria === m.categoria);
    const sola = MODELS.filter((x) => x.categoria === m.categoria).length < 2;
    // Categoria d'un sol model: comparem amb la mitjana de tots (si no, sempre seria 0 punts).
    return { m, proves, compres, conversio: conv(compres, proves), conversio_categoria: sola ? mitjana : conv(sumaCompres(cat), sumaProves(cat)) };
  });
  const ordenades = [...files].sort((a, b) => (a.conversio ?? 0) - (b.conversio ?? 0));
  return files.map((x) => {
    const rang = ordenades.indexOf(x);
    const quartil = Math.min(4, 1 + Math.floor((rang / files.length) * 4));
    const motius = Object.entries(x.m.motius).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
    return {
      model: x.m.model, nom: x.m.nom, categoria: x.m.categoria, preu: x.m.preu,
      proves: x.proves, compres: x.compres, conversio: x.conversio === null ? null : arr(x.conversio),
      conversio_categoria: x.conversio_categoria === null ? null : arr(x.conversio_categoria),
      quartil_categoria: quartil,
      molt_provat_poc_venut: x.proves >= llindar && (x.conversio ?? 1) < 0.6 * mitjana,
      venut_sense_provar: Math.round(x.proves * 0.02),
      estoc: x.m.estocTalla.reduce((s, n) => s + n, 0),
      motiu_principal: (motius[0]?.[0] as T.Motiu) ?? null,
      demanda_perduda: x.m.model === 'CL-24-NAT' ? escala(f, 5) : x.m.model === 'VV-26-VRD' ? escala(f, 2) : x.m.model === 'TX-26-IND' ? escala(f, 1) : 0,
    };
  });
}

function accio(f: FiltreMock): T.Accio | null {
  const pitjor = models(f).filter((m) => m.molt_provat_poc_venut).sort((a, b) => b.proves - a.proves)[0];
  if (!pitjor) return null;
  const fins = dataLocal(f.fins); fins.setDate(fins.getDate() + 7);
  return {
    text: `El ${pitjor.nom.toLowerCase()} es prova molt (${pitjor.proves} proves) i es ven poc (${Math.round((pitjor.conversio ?? 0) * 100)} %). El motiu més citat és el tall: revisar-lo amb el taller abans de pensar en rebaixar-lo.`,
    insight: 3, model: pitjor.model, responsable: 'Producte', data_limit: isoData(fins),
  };
}

function resum(f: FiltreMock): T.Resum {
  const c = cub(f), ca = cub(anterior(f));
  const proves = sumaProves(c), compres = sumaCompres(c);
  const pa = sumaProves(ca), cpa = sumaCompres(ca);
  const cv = conv(compres, proves), cva = conv(cpa, pa);
  const sessions = Math.round(proves / 1.6);
  const vsp = Math.round(compres * 0.038);
  const serie = dies(f.des, f.fins).map((data) => {
    const d = c.filter((x) => x.data === data);
    const p = sumaProves(d), co = sumaCompres(d);
    return { data, proves: p, compres: co, conversio: conv(co, p) === null ? null : arr(conv(co, p)!), grup_origen: grupDia(data) };
  });
  const respostes = Math.round(sessions * 1.47 * 0.12);
  return {
    periode: { des: f.des, fins: f.fins, dies: serie.length },
    kpi: {
      proves, compres_atribuides: compres, conversio: cv === null ? null : arr(cv),
      conversio_periode_anterior: cva === null ? null : arr(cva),
      variacio_conversio: cv !== null && cva !== null ? arr(cv - cva) : null,
      sessions, peces_per_sessio: sessions ? arr(proves / sessions, 1) : null,
      unitats_venudes: compres + vsp, venut_sense_provar: vsp, venut_sense_provar_pct: compres ? arr(vsp / (compres + vsp)) : null,
      peticions_talla: Math.round(sessions * 0.1), temps_resposta_mediana_s: f.botigues.length === 1 && f.botigues[0] === 'GIR-01' ? null : 92,
      pct_resposta_sota_90s: 0.48, peces_abandonades: Math.round(proves * 0.008), demanda_perduda: escala(f, 9),
      respostes_motiu: respostes, taxa_resposta_motiu: 0.12, proves_ambigues: Math.round(proves * 0.15),
    },
    serie_diaria: serie,
    accio: accio(f),
    alertes_obertes: estat.peticions.filter((p) => p.estat === 'pendent').length + estat.abandonades.filter((a) => !a.resolta).length,
  };
}

function setmanes(f: FiltreMock, n: number): { des: string; fins: string }[] {
  const r: { des: string; fins: string }[] = [];
  const fins = dataLocal(f.fins);
  const dl = new Date(fins); dl.setDate(dl.getDate() - ((dl.getDay() + 6) % 7));
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(dl); d.setDate(d.getDate() - 7 * i);
    const e = new Date(d); e.setDate(e.getDate() + 6);
    r.push({ des: isoData(d), fins: isoData(e) });
  }
  return r;
}

function modelDetall(f: FiltreMock, codi: string): T.ModelDetall | null {
  const m = defModel(codi);
  if (!m) return null;
  const c = cub(f).filter((x) => x.model === codi);
  const proves = sumaProves(c), compres = sumaCompres(c);
  const talles = m.talles.map((talla, i) => {
    const t = c.filter((x) => x.talla === talla);
    const p = sumaProves(t), co = sumaCompres(t);
    return {
      talla, gtin: `84${String(1000000000 + MODELS.indexOf(m) * 100 + i).padStart(11, '0')}`,
      proves: p, compres: co, conversio: conv(co, p) === null ? null : arr(conv(co, p)!),
      pct_proves: proves ? arr(p / proves) : null, pct_compres: compres ? arr(co / compres) : null,
      estoc: m.estocTalla[i], demanda_perduda: m.estocTalla[i] === 0 ? escala(f, 5) : 0, canvis_de_talla: Math.round(p * 0.05),
    };
  });
  const totalMotius = Object.values(m.motius).reduce((s, n) => s + (n ?? 0), 0);
  const factor = Math.max(0.3, nSetmanes(f) * (f.botigues.length / BOTIGUES.length));
  const motius = (Object.entries(m.motius) as [T.Motiu, number][])
    .map(([motiu, n]) => ({ motiu, n: Math.round(n * factor), pct: arr(n / totalMotius, 2) }))
    .filter((x) => x.n > 0)
    .sort((a, b) => b.n - a.n);
  const nMotius = motius.reduce((s, x) => s + x.n, 0);
  const serie_setmanal = setmanes(f, 6).map((s) => {
    const cs = cub({ ...f, ...s }).filter((x) => x.model === codi);
    const p = sumaProves(cs), co = sumaCompres(cs);
    return { setmana: s.des, proves: p, compres: co, conversio: conv(co, p) === null ? null : arr(conv(co, p)!) };
  });
  const sessionsFitxa = Math.max(1, Math.round((proves / 1.6) * 1.4));
  return {
    model: m.model, nom: m.nom, categoria: m.categoria, color: m.color, preu: m.preu,
    kpi: { proves, compres, conversio: conv(compres, proves) === null ? null : arr(conv(compres, proves)!), venut_sense_provar: Math.round(proves * 0.02), respostes_motiu: nMotius, taxa_resposta_motiu: arr(nMotius / sessionsFitxa, 2) },
    talles, motius, serie_setmanal,
    provat_amb: m.provatAmb.map((x, i) => ({ model: x, nom: defModel(x)!.nom, sessions: Math.max(1, Math.round(proves * (0.16 - i * 0.04))) })),
    origen: ORIGENS[codi] ?? null,
    efecte_origen: ORIGENS[codi] ? experimentOrigen(f, codi) : null,
  };
}

function tallesResp(f: FiltreMock): T.Talles {
  const c = cub(f);
  const claus = new Map<string, Cella[]>();
  for (const x of c) {
    const k = `${defModel(x.model)!.categoria}|${x.talla}`;
    const l = claus.get(k) ?? []; l.push(x); claus.set(k, l);
  }
  const taula = [...claus.entries()].map(([k, l]) => {
    const [categoria, talla] = k.split('|');
    const p = sumaProves(l), co = sumaCompres(l);
    return { categoria, talla, proves: p, compres: co, conversio: conv(co, p) === null ? null : arr(conv(co, p)!) };
  });
  const no_quadra: T.NoQuadra[] = [];
  const tx = c.filter((x) => x.model === 'TX-26-IND');
  const t38 = tx.filter((x) => x.talla === '38'), resta = tx.filter((x) => x.talla !== '38');
  const c38 = conv(sumaCompres(t38), sumaProves(t38)), cr = conv(sumaCompres(resta), sumaProves(resta));
  if (c38 !== null && cr !== null) {
    no_quadra.push({
      model: 'TX-26-IND', nom: 'Texans rectes', talla: '38', conversio: arr(c38), conversio_resta_talles: arr(cr),
      text: `Els texans en 38 es venen a 1 de cada ${Math.max(1, Math.round(1 / Math.max(c38, 0.01)))} proves; la resta de talles, a 1 de cada ${Math.round(1 / cr)}. Pot ser el patró de la 38.`,
    });
  }
  const corba = MODELS.slice(0, 5).map((m) => {
    const cm = c.filter((x) => x.model === m.model);
    const tp = sumaProves(cm), tc = sumaCompres(cm), te = m.estocTalla.reduce((s, n) => s + n, 0);
    const files = m.talles.map((talla, i) => {
      const t = cm.filter((x) => x.talla === talla);
      const pp = tp ? sumaProves(t) / tp : 0, pc = tc ? sumaCompres(t) / tc : 0;
      return { talla, pct_proves: arr(pp, 2), pct_compres: arr(pc, 2), pct_estoc: te ? arr(m.estocTalla[i] / te, 2) : null, proposta_pct: Math.round((0.7 * pc + 0.3 * pp) * 20) / 20 };
    });
    return { model: m.model, nom: m.nom, talles: files };
  });
  return { taula, no_quadra, corba };
}

function demandaPerduda(f: FiltreMock): T.DemandaPerduda {
  const per_variant = [
    { model: 'CL-24-NAT', nom: 'Camisa de lli', color: 'Natural', talla: 'L', n: escala(f, 5), estoc: 0 },
    { model: 'VV-26-VRD', nom: 'Vestit de viscosa', color: 'Verd', talla: 'XS', n: escala(f, 2), estoc: 0 },
    { model: 'TX-26-IND', nom: 'Texans rectes', color: 'Índigo', talla: '44', n: escala(f, 1), estoc: 0 },
    { model: 'JM-24-GRF', nom: 'Jersei de merino', color: 'Grafit', talla: 'XL', n: escala(f, 1), estoc: 0 },
  ].filter((x) => x.n > 0);
  const total = per_variant.reduce((s, x) => s + x.n, 0);
  return {
    total, per_variant,
    text: total ? `${total} peticions de talles que no hi eren; ${per_variant[0].n} eren la camisa de lli en L.` : 'Cap petició de talla sense estoc en aquest període.',
  };
}

function motius(f: FiltreMock): T.Motius {
  const tots = new Map<T.Motiu, number>();
  const factor = Math.max(0.3, nSetmanes(f) * (f.botigues.length / BOTIGUES.length));
  const per_model = MODELS.map((m) => {
    const ms: Partial<Record<T.Motiu, number>> = {};
    for (const [k, v] of Object.entries(m.motius) as [T.Motiu, number][]) {
      const n = Math.round(v * factor);
      if (n) { ms[k] = n; tots.set(k, (tots.get(k) ?? 0) + n); }
    }
    return { model: m.model, nom: m.nom, respostes: Object.values(ms).reduce((s, n) => s + (n ?? 0), 0), motius: ms };
  }).filter((m) => m.respostes > 0).sort((a, b) => b.respostes - a.respostes);
  const respostes = [...tots.values()].reduce((s, n) => s + n, 0);
  const sessions_fitxa = Math.round(respostes / 0.12);
  return {
    respostes, sessions_fitxa, taxa_resposta: sessions_fitxa ? arr(respostes / sessions_fitxa, 2) : null,
    per_motiu: [...tots.entries()].map(([motiu, n]) => ({ motiu, n, pct: arr(n / respostes, 2) })).sort((a, b) => b.n - a.n),
    per_model,
  };
}

function servei(f: FiltreMock): T.Servei {
  const r = resum(f);
  const pet = r.kpi.peticions_talla;
  const mapa: T.CellaOcupacio[] = [];
  for (let d = 0; d < 6; d++) {
    for (let h = 10; h <= 20; h++) {
      const rnd = atzar(`oc${d}${h}${f.botigues.join()}`);
      const pic = (h >= 12 && h <= 13) || (h >= 17 && h <= 19) ? 1.8 : 1;
      const sessions = Math.round((2 + rnd() * 4) * pic * (d === 5 ? 1.7 : 1) * nSetmanes(f) * (f.botigues.length / 3) * 1.4);
      mapa.push({ dia_setmana: d, hora: h, sessions, pct_totes_plenes: arr(Math.min(0.9, Math.max(0, (pic - 1) * 0.25 + (d === 5 ? 0.25 : 0) + rnd() * 0.08 - 0.04)), 2) });
    }
  }
  const sessions = r.kpi.sessions;
  const reparticio = [0.42, 0.3, 0.16, 0.08, 0.04];
  return {
    peticions: pet, peticions_per_sessio: sessions ? arr(pet / sessions, 2) : null, mediana_s: r.kpi.temps_resposta_mediana_s, pct_sota_90s: r.kpi.pct_resposta_sota_90s,
    per_estat: { pendent: estat.peticions.filter((p) => p.estat === 'pendent').length, en_cami: estat.peticions.filter((p) => p.estat === 'en_cami').length, lliurada: Math.round(pet * 0.85), no_disponible: Math.round(pet * 0.11) },
    ocupacio: { durada_mitjana_s: 340, pct_temps_totes_plenes: 0.06, mapa },
    peces_per_sessio: reparticio.map((p, i) => ({ peces: i + 1, sessions: Math.round(sessions * p), pct_amb_compra: arr(0.22 + i * 0.09, 2) })),
  };
}

function estoc(f: FiltreMock): T.Estoc {
  const llista = models(f);
  return {
    parat: [
      { gtin: '8400000000412', model: 'PL-26-TER', nom: 'Pantaló de lli', talla: '44', unitats: 4, dies_sense_activitat: 26 },
      { gtin: '8400000000300', model: 'SB-25-CRU', nom: 'Sobrecamisa de cotó', talla: 'XS', unitats: 1, dies_sense_activitat: 23 },
      { gtin: '8400000000104', model: 'VV-26-VRD', nom: 'Vestit de viscosa', talla: 'L', unitats: 2, dies_sense_activitat: 22 },
    ],
    risc_rebaixa: llista.filter((m) => m.quartil_categoria === 1).map((m) => ({
      model: m.model, nom: m.nom, unitats: m.estoc * f.botigues.length, cobertura_setmanes: arr((m.estoc * f.botigues.length) / Math.max(0.5, m.compres / nSetmanes(f)), 1), conversio: m.conversio, quartil_categoria: 1,
    })).filter((m) => (m.cobertura_setmanes ?? 0) > 1),
    precisio: { recomptes: 3, error_mitja_pct: 0.04 },
  };
}

function fitxaNfc(f: FiltreMock): T.FitxaNfc {
  const sessions = resum(f).kpi.sessions;
  const tocs = Math.round(sessions * 1.53);
  const sec: [T.Seccio, number][] = [['talles', 0.31], ['origen', 0.23], ['peticio_talla', 0.17], ['cura', 0.13], ['motiu', 0.11], ['preguntes', 0.05]];
  const idi: [string, number][] = [['ca', 0.58], ['es', 0.24], ['en', 0.09], ['fr', 0.07], ['de', 0.02]];
  return {
    tocs, sessions_cabina: sessions, tocs_per_sessio: sessions ? arr(tocs / sessions, 1) : null,
    seccions: sec.map(([seccio, p]) => ({ seccio, n: Math.round(tocs * p), pct: p })),
    idiomes: idi.map(([idioma, p]) => ({ idioma, n: Math.round(tocs * p), pct: p })),
  };
}

function alertes(): T.RespostaAlertes {
  return {
    alertes: [
      ...estat.peticions.filter((p) => p.estat === 'pendent').map((p) => ({ id: `pt-${p.id}`, tipus: 'peticio_talla' as const, text: `Cabina ${p.cabina.slice(-1)} demana ${p.nom.toLowerCase()} en ${p.talla}.`, botiga_id: 'BCN-01', cabina: p.cabina, creada: p.hora_peticio, estat: 'pendent', ref: p.id })),
      ...estat.abandonades.filter((a) => !a.resolta).map((a) => ({ id: `ab-${a.id}`, tipus: 'peca_abandonada' as const, text: `${a.nom} (${a.talla}) fa més de 30 min fora de la sala.`, botiga_id: 'BCN-01', cabina: a.cabina, creada: a.detectada, estat: 'pendent', ref: a.id })),
      { id: 'mp-VV', tipus: 'molt_provat_poc_venut' as const, text: 'El vestit de viscosa es prova molt i es ven poc aquesta setmana.', botiga_id: 'BCN-01', cabina: null, creada: new Date().toISOString(), estat: 'pendent', ref: 'VV-26-VRD' },
    ],
  };
}

function valor(): T.Valor {
  const p = Object.fromEntries(['marge_peca', 'quota_mensual', 'pvp_mitja'].map((k) => [k, Number(estat.parametres[k]) || 0]));
  const marge = p.marge_peca, pvp = p.pvp_mitja;
  const fmt = (n: number) => n.toLocaleString('ca-ES');
  return {
    parametres: p,
    llindar_peces_mes: marge ? Math.ceil(p.quota_mensual / marge) : null,
    palanques: [
      { palanca: 'Menys talles esgotades', insights: [7], formula: 'Peticions sense estoc × % reposat a temps × % que compra × marge per peça', valor_eur: 60 * 0.5 * 0.4 * marge, detall: `60 × 50 % × 40 % × ${fmt(marge)} € al mes`, es_estimacio: true },
      { palanca: 'Més conversió', insights: [2, 17, 18], formula: 'Punts de conversió guanyats × proves al mes × marge per peça', valor_eur: 0.02 * 1600 * marge, detall: `2 punts × 1.600 proves × ${fmt(marge)} € al mes`, es_estimacio: true },
      { palanca: 'Menys rebaixes', insights: [3, 14, 15], formula: 'Unitats detectades a temps × PVP × (descompte evitat − descompte final)', valor_eur: 40 * pvp * 0.3, detall: `40 u × ${fmt(pvp)} € × (40 % − 10 %) per temporada`, es_estimacio: true },
      { palanca: 'Millor recompra', insights: [5, 6], formula: 'Unitats sobrants evitades per talla × cost unitari × % que s’hauria liquidat', valor_eur: 30 * 25 * 0.6, detall: '30 u × 25 € × 60 % per comanda', es_estimacio: true },
      { palanca: 'Disseny', insights: [8, 22], formula: 'Unitats no produïdes d’un tall que no funciona × cost', valor_eur: null, detall: 'Difícil de posar en euros', es_estimacio: true },
      { palanca: 'Compliment a França', insights: [24], formula: 'Hores estalviades a la declaració Refashion × cost per hora', valor_eur: null, detall: 'Preparem les dades; no fem la declaració', es_estimacio: true },
    ],
  };
}

function informe(f: FiltreMock, tipus: T.TipusInforme): T.Informe | null {
  const r = resum(f), ms = models(f), t = tallesResp(f), dp = demandaPerduda(f), mo = motius(f), s = servei(f);
  const xifres: T.BlocInforme = { id: 'xifres', titol: 'Tres xifres', text: `${r.kpi.proves} proves, ${r.kpi.compres_atribuides} compres després de provar: conversió del ${Math.round((r.kpi.conversio ?? 0) * 100)} %.`, dades: { proves: r.kpi.proves, compres: r.kpi.compres_atribuides, conversio: r.kpi.conversio, variacio_conversio: r.kpi.variacio_conversio } };
  const top: T.BlocInforme = { id: 'molt_provat', titol: 'Molt provat, poc venut', text: 'Els models que més es proven i menys es venen, comparats amb la seva categoria.', dades: [...ms].sort((a, b) => (a.conversio ?? 0) - (b.conversio ?? 0)).slice(0, 5).map((m) => ({ model: m.nom, proves: m.proves, compres: m.compres, conversio: m.conversio, conversio_categoria: m.conversio_categoria })) };
  const nq: T.BlocInforme = { id: 'talla_no_quadra', titol: 'La talla que no quadra', text: t.no_quadra[0]?.text ?? 'Cap talla per sota de la resta aquesta setmana.', dades: t.no_quadra.map((x) => ({ model: x.nom, talla: x.talla, conversio: x.conversio, conversio_resta_talles: x.conversio_resta_talles })) };
  const dpb: T.BlocInforme = { id: 'demanda_perduda', titol: 'Demanda perduda', text: dp.text, dades: dp.per_variant.map((x) => ({ model: x.nom, color: x.color, talla: x.talla, peticions: x.n })) };
  const mob: T.BlocInforme = { id: 'motius', titol: 'Per què no se l’emporten', text: `${mo.respostes} respostes de ${mo.sessions_fitxa} sessions amb la fitxa oberta (taxa de resposta del ${Math.round((mo.taxa_resposta ?? 0) * 100)} %).`, dades: mo.per_motiu.map((x) => ({ motiu: x.motiu, respostes: x.n, pct: x.pct })) };
  const sb: T.BlocInforme = { id: 'servei', titol: 'Servei a la cabina', text: `${s.peticions} peticions de talla; mediana de resposta ${s.mediana_s ?? '—'} s; ${Math.round((s.pct_sota_90s ?? 0) * 100)} % per sota de 90 s.`, dades: { peticions: s.peticions, mediana_s: s.mediana_s, pct_sota_90s: s.pct_sota_90s } };
  const exp = experimentOrigen(f);
  const origen: T.BlocInforme = { id: 'prova_origen', titol: 'Prova en curs: l’origen fa vendre?', text: exp.conclusio, dades: Object.entries(exp.grups).map(([g, v]) => ({ grup: g === 'amb' ? 'Amb origen' : 'Sense origen', ...v })) };
  const avisos = [
    ...(Object.values(exp.grups).some((g) => g.proves < 30) ? ['Mostra petita: algun grup de la prova d’origen té menys de 30 proves.'] : []),
    'Vendes per CSV: les compres de Girona arriben amb un dia de retard.',
    `${r.kpi.proves_ambigues} proves ambigües (lectures que podien ser de la cabina del costat) no s’han comptat.`,
  ];
  const blocsPer: Record<T.TipusInforme, T.BlocInforme[]> = {
    diari: [xifres, sb, dpb],
    setmanal: [xifres, top, nq, dpb, mob, sb],
    mensual: [
      { id: 'decisions', titol: 'Registre de decisions', text: 'Les decisions del mes i què n’ha sortit.', dades: estat.decisions.map((d) => ({ decisio: d.titol, estat: d.estat, resultat: d.resultat ?? '—' })) },
      { id: 'conversio_categoria', titol: 'Conversió per categoria i talla', text: 'Les talles amb menys conversió de cada categoria.', dades: [...t.taula].sort((a, b) => (a.conversio ?? 0) - (b.conversio ?? 0)).slice(0, 6) },
      { id: 'estoc', titol: 'Estoc parat i risc de rebaixa', text: 'Unitats sense cap prova ni venda en 21 dies.', dades: estoc(f).parat.map((x) => ({ model: x.nom, talla: x.talla, unitats: x.unitats, dies: x.dies_sense_activitat })) },
      origen,
      { id: 'valor', titol: 'Valor estimat', text: 'Estimació amb els paràmetres de la marca; no és un resultat.', dades: valor().palanques.filter((p) => p.valor_eur !== null).map((p) => ({ palanca: p.palanca, valor_eur: p.valor_eur, detall: p.detall })) },
    ],
    temporada: [top, origen, dpb, { id: 'pais', titol: 'Unitats per país de fabricació', text: 'On s’han confeccionat les peces venudes.', dades: [{ pais: 'Portugal', unitats: 212 }, { pais: 'Espanya', unitats: 168 }, { pais: 'Marroc', unitats: 97 }] }],
    pilot: [
      { id: 'criteris', titol: 'Criteris d’èxit', text: 'Els criteris acordats abans del pilot i on som.', dades: [{ criteri: 'Proves de confiança alta o mitjana', objectiu: '≥ 85 %', resultat: '85 %', compleix: 'Sí' }, { criteri: 'Decisions preses amb dades', objectiu: '≥ 3', resultat: String(estat.decisions.length), compleix: 'Sí' }, { criteri: 'Temps de resposta mediana', objectiu: '≤ 90 s', resultat: '92 s', compleix: 'No' }] },
      xifres, origen,
      { id: 'no_afirmar', titol: 'Què no podem afirmar', text: 'Amb aquestes dades no podem dir que l’origen faci vendre més (la prova no és concloent), ni extrapolar a botigues sense lector.', dades: null },
    ],
    mango: [xifres, origen, { id: 'ultim_metre', titol: 'L’últim metre de l’origen', text: 'El 23 % dels tocs de la fitxa obren la secció d’origen.', dades: fitxaNfc(f).seccions } ],
  };
  const titols: Record<T.TipusInforme, string> = { diari: 'Resum diari', setmanal: 'Informe setmanal', mensual: 'Informe mensual d’accions', temporada: 'Informe de fi de temporada', pilot: 'Informe final del pilot', mango: 'Pilot de Mango' };
  if (!blocsPer[tipus]) return null;
  return { tipus, titol: titols[tipus], periode: r.periode, blocs: blocsPer[tipus], accio: r.accio, avisos };
}

// ── Encaminador ──────────────────────────────────────────────────────────
export function respon(metode: string, url: URL, cos: unknown): Resposta {
  const ruta = url.pathname.replace(/^\/api\/v2/, '');
  const q = url.searchParams;
  const u = usuariActual();

  if (ruta === '/sessio' && metode === 'POST') {
    const c = cos as { correu?: string; contrasenya?: string };
    if (!c?.correu || !c?.contrasenya) return error(400, 'Escriu el correu i la contrasenya.');
    if (c.contrasenya === 'malament') return error(401, 'El correu o la contrasenya no són correctes.');
    const rol = c.correu.startsWith('botiga') ? 'botiga' : 'marca';
    desaSessio(rol);
    return ok({ usuari: rol === 'botiga' ? USUARI_BOTIGA : USUARI_MARCA });
  }
  if (!u) return error(401, 'Cal entrar.');
  if (ruta === '/sessio' && metode === 'DELETE') { desaSessio('fora'); return ok({ ok: true }); }
  if (ruta === '/jo') return ok({ usuari: u, botigues: u.rol === 'botiga' ? BOTIGUES.filter((b) => b.id === u.botiga_id) : BOTIGUES });

  const fq = new URLSearchParams(q);
  if (u.rol === 'botiga') fq.set('botiga', u.botiga_id ?? 'BCN-01');
  const f = filtre(fq);
  const model = ruta.match(/^\/models\/(.+)$/);
  const informeM = ruta.match(/^\/informes\/(\w+)$/);
  const peticioM = ruta.match(/^\/peticions\/(\d+)$/);
  const abandM = ruta.match(/^\/abandonades\/(\d+)$/);
  const decM = ruta.match(/^\/decisions\/(\d+)$/);

  if (metode === 'GET') {
    switch (ruta) {
      case '/resum': return ok(resum(f));
      case '/models': return ok({ models: models(f) });
      case '/talles': return ok(tallesResp(f));
      case '/demanda-perduda': return ok(demandaPerduda(f));
      case '/motius': return ok(motius(f));
      case '/servei': return ok(servei(f));
      case '/estoc': return ok(estoc(f));
      case '/fitxa-nfc': return ok(fitxaNfc(f));
      case '/experiments': return ok({ experiments: [experimentOrigen(f), EXPERIMENT_ACABAT] });
      case '/alertes': return ok(alertes());
      case '/valor': return ok(valor());
      case '/peticions': return ok({ peticions: estat.peticions.filter((p) => !q.get('estat') || p.estat === q.get('estat')).map((p) => ({ ...p, segons_espera: Math.round((Date.now() - Date.parse(p.hora_peticio)) / 1000) })) });
      case '/abandonades': return ok({ abandonades: estat.abandonades.filter((a) => !q.get('obertes') || !a.resolta) });
      case '/decisions': return ok({ decisions: estat.decisions });
      case '/parametres': return ok({ botiga_id: '*', valors: estat.parametres });
    }
    if (model) { const d = modelDetall(f, decodeURIComponent(model[1])); return d ? ok(d) : error(404, 'Aquest model no existeix al catàleg.'); }
    if (informeM) { const i = informe(f, informeM[1] as T.TipusInforme); return i ? ok(i) : error(404, 'Aquest tipus d’informe no existeix.'); }
  }
  if (metode === 'PATCH' && peticioM) {
    const p = estat.peticions.find((x) => x.id === Number(peticioM[1]));
    if (!p) return error(404, 'Aquesta petició ja no hi és.');
    p.estat = (cos as { estat: T.EstatPeticio }).estat;
    return ok(p);
  }
  if (metode === 'PATCH' && abandM) {
    const a = estat.abandonades.find((x) => x.id === Number(abandM[1]));
    if (!a) return error(404, 'Aquesta peça ja no hi és.');
    a.resolta = true;
    return ok(a);
  }
  if (ruta === '/decisions' && metode === 'POST') {
    const c = cos as T.NovaDecisio;
    if (!c.titol?.trim()) return error(400, 'La decisió necessita un títol.');
    const d: T.Decisio = { ...c, id: estat.seguentDecisio++, creada: new Date().toISOString() };
    estat.decisions.unshift(d);
    return ok(d);
  }
  if (metode === 'PATCH' && decM) {
    const d = estat.decisions.find((x) => x.id === Number(decM[1]));
    if (!d) return error(404, 'Aquesta decisió no existeix.');
    Object.assign(d, cos);
    return ok(d);
  }
  if (ruta === '/experiments' && metode === 'POST') {
    if (u.rol === 'botiga') return error(403, 'Només la marca pot crear proves.');
    const c = cos as T.NouExperiment;
    if (!c.id || !/^[a-z0-9-]+$/.test(c.id)) return error(400, 'L\u2019identificador només pot tenir minúscules, xifres i guions.');
    return ok({ ...EXPERIMENT_ACABAT, ...c, estat: 'planificat', grups: { amb: { proves: 0, compres: 0, conversio: null }, sense: { proves: 0, compres: 0, conversio: null } }, diferencia: null, ic95: null, p_valor: null, mostra_suficient: false, proves_necessaries: null, conclusio: 'Prova creada: el sorteig de dies ja està fet.' });
  }
  if (ruta === '/parametres' && metode === 'PUT') {
    if (u.rol === 'botiga') return error(403, 'Només la marca pot canviar els paràmetres.');
    Object.assign(estat.parametres, (cos as T.Parametres).valors);
    return ok({ botiga_id: '*', valors: estat.parametres });
  }
  const imp = ruta.match(/^\/importa\/(vendes|estoc|cataleg)$/);
  if (imp && metode === 'POST') {
    if (imp[1] === 'cataleg' && u.rol !== 'admin') return error(403, 'Només un administrador pot importar el catàleg.');
    return ok({ importades: 0, errors: [] }); // el recompte real el fa index.ts, que llegeix el fitxer
  }
  if (ruta === '/shopify/sincronitza' && metode === 'POST') {
    if (u.rol !== 'admin') return error(403, 'Només un administrador pot sincronitzar Shopify.');
    return ok({ comandes: 23, linies: 31, estoc: 214 });
  }
  return error(404, `Ruta desconeguda al mode demostració: ${metode} ${ruta}`);
}

export { BOTIGUES as BOTIGUES_MOCK, MODELS as MODELS_MOCK };
