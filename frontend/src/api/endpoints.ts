/** Una funció per ruta de docs/API.md, amb el tipus de resposta. */
import { api, construeixUrl, descarrega, paramsFiltre } from './client';
import type * as T from './types';

const f = paramsFiltre;
const enc = encodeURIComponent;

export const sessio = {
  entra: (correu: string, contrasenya: string) => api.post<T.RespostaSessio>('/sessio', { correu, contrasenya }),
  surt: () => api.del<{ ok: boolean }>('/sessio'),
  jo: () => api.get<T.RespostaJo>('/jo'),
};

export const lotProva = {
  estat: (s?: AbortSignal) => api.get<T.EstatLotProva>('/lot-prova', undefined, s),
  carrega: () => api.post<T.EstatLotProva>('/lot-prova', {}),
  esborra: () => api.del<{ esborrat: boolean; files: number }>('/lot-prova'),
};

export const analitica = {
  resum: (x: T.Filtre, s?: AbortSignal) => api.get<T.Resum>('/resum', f(x), s),
  panorama: (x: T.Filtre, s?: AbortSignal) => api.get<T.Panorama>('/panorama', f(x), s),
  models: (x: T.Filtre, s?: AbortSignal) => api.get<T.RespostaModels>('/models', f(x), s),
  model: (x: T.Filtre, model: string, s?: AbortSignal) => api.get<T.ModelDetall>(`/models/${enc(model)}`, f(x), s),
  talles: (x: T.Filtre, s?: AbortSignal) => api.get<T.Talles>('/talles', f(x), s),
  demandaPerduda: (x: T.Filtre, s?: AbortSignal) => api.get<T.DemandaPerduda>('/demanda-perduda', f(x), s),
  motius: (x: T.Filtre, s?: AbortSignal) => api.get<T.Motius>('/motius', f(x), s),
  servei: (x: T.Filtre, s?: AbortSignal) => api.get<T.Servei>('/servei', f(x), s),
  estoc: (x: T.Filtre, s?: AbortSignal) => api.get<T.Estoc>('/estoc', f(x), s),
  fitxaNfc: (x: T.Filtre, s?: AbortSignal) => api.get<T.FitxaNfc>('/fitxa-nfc', f(x), s),
  experiments: (x: T.Filtre, s?: AbortSignal) => api.get<T.RespostaExperiments>('/experiments', f(x), s),
  alertes: (x: T.Filtre, s?: AbortSignal) => api.get<T.RespostaAlertes>('/alertes', f(x), s),
  valor: (x: T.Filtre, s?: AbortSignal) => api.get<T.Valor>('/valor', f(x), s),
  estatSistema: (x: T.Filtre, s?: AbortSignal) => api.get<T.EstatSistema>('/estat-sistema', f(x), s),
  informe: (x: T.Filtre, tipus: T.TipusInforme, s?: AbortSignal) => api.get<T.Informe>(`/informes/${tipus}`, f(x), s),
  triaGrafics: (x: T.Filtre, tipus: T.TipusInforme, grafics: string[] | null) =>
    api.put<{ tipus: string; grafics_triats: string[] | null }>(`/informes/${tipus}/grafics`, { grafics }, f(x)),
  comparativa: (x: T.Filtre, o: { compara?: string; colleccio?: number; franja?: string; condicio?: string }, s?: AbortSignal) =>
    api.get<T.Comparativa>('/comparativa', { ...f(x), ...o }, s),
  provadorOnline: (x: T.Filtre, s?: AbortSignal, model?: string) => api.get<T.ProvadorOnline>('/provador-online', { ...f(x), model }, s),
  colleccions: (s?: AbortSignal) => api.get<T.Colleccio[]>('/colleccions', undefined, s),
  novaColleccio: (c: { nom: string; des: string; fins: string }) => api.post<T.Colleccio>('/colleccions', c),
  esborraColleccio: (id: number) => api.del<{ ok: boolean }>(`/colleccions/${id}`),
  condicions: (botiga?: string | null, s?: AbortSignal) => api.get<T.CondicioDia[]>('/condicions', { botiga: botiga ?? undefined }, s),
  novaCondicio: (c: { botiga_id?: string | null; data: string; condicio: string }) => api.post<{ ok: boolean }>('/condicions', c),
  esborraCondicio: (data: string, condicio: string, botiga?: string | null) =>
    api.del<{ ok: boolean }>('/condicions', { data, condicio, botiga: botiga ?? undefined }),
  historial: (epc: string) => api.get<T.HistorialPeca>(`/peces/${enc(epc)}/historial`),
  perdues: (x: T.Filtre) => api.get<T.Perdues>('/perdues', f(x)),
  sessions: (x: T.Filtre, s?: AbortSignal) => api.get<T.Sessions>('/sessions', f(x), s),
  estocParatCsv: (x: T.Filtre & { categoria?: string }) => descarrega('/estoc/parat.csv', { ...f(x), categoria: x.categoria }),
};

/** Provadors en directe (B). */
export const provadors = {
  directe: (botiga?: string, s?: AbortSignal) => api.get<T.ProvadorsDirecte>('/provadors/directe', { botiga }, s),
};

/** Tasques de botiga (D.1). */
export const tasques = {
  llista: (botiga?: string, estat?: T.EstatTasca, s?: AbortSignal) => api.get<T.RespostaTasques>('/tasques', { botiga, estat }, s),
  crea: (t: T.NovaTasca) => api.post<T.Tasca>('/tasques', t),
  canvia: (id: number, estat: Exclude<T.EstatTasca, 'pendent'>) => api.patch<T.Tasca>(`/tasques/${id}`, { estat }),
};

/** Fitxa NFC configurable (A.3). */
/** v0.5: la foto de cada model (i color) que veu el client a la fitxa NFC. */
export const imatges = {
  llista: (s?: AbortSignal) => api.get<{ imatges: T.ImatgePeca[] }>('/imatges', undefined, s),
  puja: (model: string, color: string, cos: { data_url: string } | { url: string }) =>
    api.put<T.ImatgeDesada>(`/imatges/${enc(model)}`, cos, color ? { color } : undefined),
  esborra: (model: string, color: string) => api.del<{ esborrada: boolean }>(`/imatges/${enc(model)}${color ? `?color=${enc(color)}` : ''}`),
  afegeixGaleria: (model: string, cos: { data_url: string } | { url: string }) =>
    api.post<{ model: string; clau: string; url: string }>(`/imatges/${enc(model)}/galeria`, cos),
  esborraGaleria: (model: string, clau: string) => api.del<{ esborrada: boolean }>(`/imatges/${enc(model)}/galeria/${enc(clau)}`),
};

export const fitxa = {
  config: (botiga?: string, s?: AbortSignal) => api.get<T.RespostaConfigFitxa>('/fitxa/config', { botiga }, s),
  desaConfig: (c: T.ConfigFitxa | T.ConfigFitxaParcial, botiga?: string) => api.put<T.RespostaConfigFitxa>('/fitxa/config', c, { botiga }),
  models: (s?: AbortSignal) => api.get<{ models: T.ModelFitxa[] }>('/fitxa/models', undefined, s),
  model: (model: string, s?: AbortSignal) => api.get<T.DetallModelFitxa>(`/fitxa/models/${enc(model)}`, undefined, s),
  desaContingut: (model: string, idioma: string, c: T.ContingutModel) => api.put<{ ok: boolean }>(`/fitxa/models/${enc(model)}/${enc(idioma)}`, c),
  /** Adreça per a un iframe (HTML de la fitxa, sense registrar esdeveniments). */
  urlPrevisualitza: (model: string, botiga: string | undefined, idioma: string) => construeixUrl('/fitxa/previsualitza', { model, botiga, idioma }),
};

/** Informes lliurats, programació, PDF i correu (E.4). */
export const informes = {
  lliurats: (botiga?: string, tipus?: T.TipusInforme, s?: AbortSignal) => api.get<T.RespostaLliurats>('/informes/lliurats', { botiga, tipus }, s),
  lliurat: (id: number, s?: AbortSignal) => api.get<T.Informe>(`/informes/lliurats/${id}`, undefined, s),
  generaAra: (c: { tipus: T.TipusInforme; botiga?: string | null; des: string; fins: string }) => api.post<T.InformeLliurat>('/informes/lliurats', c),
  pdfLliurat: (id: number) => descarrega(`/informes/lliurats/${id}.pdf`),
  pdf: (tipus: T.TipusInforme, x: T.Filtre) => descarrega(`/informes/${tipus}.pdf`, f(x)),
  enviaLliurat: (id: number, destinataris: string[]) => api.post<{ ok: boolean }>(`/informes/lliurats/${id}/envia`, { destinataris }),
  envia: (tipus: T.TipusInforme, x: T.Filtre, destinataris: string[]) => api.post<{ ok: boolean }>(`/informes/${tipus}/envia`, { destinataris }, f(x)),
  programacio: (botiga?: string, s?: AbortSignal) => api.get<T.RespostaProgramacio>('/informes/programacio', { botiga }, s),
  creaProgramacio: (p: T.NovaProgramacio) => api.post<T.Programacio>('/informes/programacio', p),
  canviaProgramacio: (id: number, p: Partial<T.NovaProgramacio>) => api.patch<T.Programacio>(`/informes/programacio/${id}`, p),
  esborraProgramacio: (id: number) => api.del<{ ok: boolean }>(`/informes/programacio/${id}`),
};

/** Integracions (F.3). */
export const integracions = {
  llista: (s?: AbortSignal) => api.get<{ integracions: T.Integracio[] }>('/integracions', undefined, s),
  crea: (i: T.NovaIntegracio) => api.post<T.Integracio>('/integracions', i),
  canvia: (id: number, c: T.CanviIntegracio) => api.patch<T.Integracio>(`/integracions/${id}`, c),
  esborra: (id: number) => api.del<{ ok: boolean }>(`/integracions/${id}`),
  prova: (c: { proveidor: T.Proveidor; config: Record<string, unknown>; secret?: string | null; id?: number; botiga_id?: string | null }) => api.post<T.ResultatProvaIntegracio>('/integracions/prova', c),
  sincronitza: (id: number) => api.post<{ resum: T.ResumSync }>(`/integracions/${id}/sincronitza`),
  registre: (id: number, s?: AbortSignal) => api.get<{ registre: T.RegistreSync[] }>(`/integracions/${id}/registre`, undefined, s),
};

export const devolucions = {
  mapa: (s?: AbortSignal) => api.get<T.MapaDevolucions>('/devolucions/mapa', undefined, s),
  desaMapa: (codi: string, motiu: string, sentit: 'petita' | 'gran' | null) =>
    api.put<T.CodiDevolucio>('/devolucions/mapa', { codi, motiu, sentit }),
  esborra: () => api.del<{ esborrades: number }>('/devolucions'),
};

export const operacio = {
  peticions: (botiga?: string, estat?: T.EstatPeticio) => api.get<T.RespostaPeticions>('/peticions', { botiga, estat }),
  canviaPeticio: (id: number, estat: Exclude<T.EstatPeticio, 'pendent'>) => api.patch<T.Peticio>(`/peticions/${id}`, { estat }),
  abandonades: (botiga?: string) => api.get<T.RespostaAbandonades>('/abandonades', { botiga, obertes: 1 }),
  recull: (id: number) => api.patch<T.Abandonada>(`/abandonades/${id}`, { resolta: true }),
  decisions: (x: T.Filtre) => api.get<T.RespostaDecisions>('/decisions', f(x)),
  creaDecisio: (d: T.NovaDecisio) => api.post<T.Decisio>('/decisions', d),
  canviaDecisio: (id: number, canvis: Partial<T.NovaDecisio>) => api.patch<T.Decisio>(`/decisions/${id}`, canvis),
  creaExperiment: (e: T.NouExperiment) => api.post<T.Experiment>('/experiments', e),
  importa: (tipus: 'vendes' | 'estoc' | 'cataleg' | 'devolucions', fitxer: File) => api.puja<T.ResultatImport>(`/importa/${tipus}`, fitxer),
  parametres: (botiga?: string) => api.get<T.Parametres>('/parametres', { botiga }),
  desaParametres: (p: T.Parametres) => api.put<T.Parametres>('/parametres', p),
  sincronitzaShopify: (botiga?: string) => api.post<T.ResultatShopify>('/shopify/sincronitza', undefined, { botiga }),
};
