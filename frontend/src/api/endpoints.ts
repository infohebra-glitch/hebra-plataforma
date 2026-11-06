/** Una funció per ruta de docs/API.md, amb el tipus de resposta. */
import { api, paramsFiltre } from './client';
import type * as T from './types';

const f = paramsFiltre;
const enc = encodeURIComponent;

export const sessio = {
  entra: (correu: string, contrasenya: string) => api.post<T.RespostaSessio>('/sessio', { correu, contrasenya }),
  surt: () => api.del<{ ok: boolean }>('/sessio'),
  jo: () => api.get<T.RespostaJo>('/jo'),
};

export const analitica = {
  resum: (x: T.Filtre, s?: AbortSignal) => api.get<T.Resum>('/resum', f(x), s),
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
  informe: (x: T.Filtre, tipus: T.TipusInforme, s?: AbortSignal) => api.get<T.Informe>(`/informes/${tipus}`, f(x), s),
  historial: (epc: string) => api.get<T.HistorialPeca>(`/peces/${enc(epc)}/historial`),
  perdues: (x: T.Filtre) => api.get<T.Perdues>('/perdues', f(x)),
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
  importa: (tipus: 'vendes' | 'estoc' | 'cataleg', fitxer: File) => api.puja<T.ResultatImport>(`/importa/${tipus}`, fitxer),
  parametres: (botiga?: string) => api.get<T.Parametres>('/parametres', { botiga }),
  desaParametres: (p: T.Parametres) => api.put<T.Parametres>('/parametres', p),
  sincronitzaShopify: (botiga?: string) => api.post<T.ResultatShopify>('/shopify/sincronitza', undefined, { botiga }),
};
