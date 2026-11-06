/**
 * Tipus de l'API del tauler (/api/v2). Mirall de docs/API.md: si el contracte
 * canvia, canvia primer allà i després aquí.
 *
 * Convencions: dates «AAAA-MM-DD» (string), hores ISO 8601 (string),
 * percentatges com a fracció 0-1 o null si no hi ha denominador, diners en euros.
 */

export type Fraccio = number | null;
export type Data = string;
export type DataHora = string;

// ── Sessió ───────────────────────────────────────────────────────────────
export type Rol = 'admin' | 'marca' | 'botiga';

export interface Usuari {
  id: number | string;
  nom: string;
  correu: string;
  rol: Rol;
  botiga_id: string | null;
}

export interface Botiga {
  id: string;
  nom: string;
  nivell: string;
}

export interface RespostaSessio { usuari: Usuari }
export interface RespostaJo { usuari: Usuari; botigues: Botiga[] }

/** Filtre comú de totes les rutes d'analítica. */
export interface Filtre {
  botiga?: string;
  des?: Data;
  fins?: Data;
}

// ── Comuns ───────────────────────────────────────────────────────────────
export interface Periode { des: Data; fins: Data; dies: number }

export interface Accio {
  text: string;
  insight: number | string | null;
  model: string | null;
  responsable: string | null;
  data_limit: Data | null;
}

export type GrupOrigen = 'amb' | 'sense';

export interface GrupExperiment { proves: number; compres: number; conversio: Fraccio }

export type EstatExperiment = 'actiu' | 'acabat' | 'planificat' | string;

export interface Experiment {
  id: string;
  variable: string;
  hipotesi: string;
  unitat: string;
  inici: Data;
  fi: Data;
  estat: EstatExperiment;
  grups: Record<string, GrupExperiment>;
  diferencia: number | null;
  ic95: [number, number] | null;
  p_valor: number | null;
  proves_minimes: number;
  mostra_suficient: boolean;
  proves_necessaries: number | null;
  setmanes_restants: number | null;
  conclusio: string;
}

// ── GET /resum ───────────────────────────────────────────────────────────
export interface KpiResum {
  proves: number;
  compres_atribuides: number;
  conversio: Fraccio;
  conversio_periode_anterior: Fraccio;
  variacio_conversio: number | null;
  sessions: number;
  peces_per_sessio: number | null;
  unitats_venudes: number;
  venut_sense_provar: number;
  venut_sense_provar_pct: Fraccio;
  peticions_talla: number;
  temps_resposta_mediana_s: number | null;
  pct_resposta_sota_90s: Fraccio;
  peces_abandonades: number;
  demanda_perduda: number;
  respostes_motiu: number;
  taxa_resposta_motiu: Fraccio;
  proves_ambigues: number;
}

export interface PuntDiari {
  data: Data;
  proves: number;
  compres: number;
  conversio: Fraccio;
  grup_origen: GrupOrigen | null;
}

export interface Resum {
  periode: Periode;
  kpi: KpiResum;
  serie_diaria: PuntDiari[];
  accio: Accio | null;
  alertes_obertes: number;
}

// ── GET /models ──────────────────────────────────────────────────────────
export type Motiu = 'talla' | 'tall' | 'preu' | 'color' | 'qualitat' | 'altre';

export interface ModelResum {
  model: string;
  nom: string;
  categoria: string;
  preu: number;
  proves: number;
  compres: number;
  conversio: Fraccio;
  conversio_categoria: Fraccio;
  quartil_categoria: number | null;
  molt_provat_poc_venut: boolean;
  venut_sense_provar: number;
  estoc: number;
  motiu_principal: Motiu | null;
  demanda_perduda: number;
}

export interface RespostaModels { models: ModelResum[] }

// ── GET /models/{model} ──────────────────────────────────────────────────
export interface TallaModel {
  talla: string;
  gtin: string;
  proves: number;
  compres: number;
  conversio: Fraccio;
  pct_proves: Fraccio;
  pct_compres: Fraccio;
  estoc: number;
  demanda_perduda: number;
  canvis_de_talla: number;
}

export interface MotiuCompte { motiu: Motiu; n: number; pct: Fraccio }

export interface PuntSetmanal { setmana: Data; proves: number; compres: number; conversio: Fraccio }

export interface ProvatAmb { model: string; nom: string; sessions: number }

export interface EtapaOrigen { etapa: string; pais: string; regio: string }
export interface Composicio { material: string; pct: number; pais: string }
export interface Origen { etapes: EtapaOrigen[]; composicio: Composicio[] }

export interface ModelDetall {
  model: string;
  nom: string;
  categoria: string;
  color: string;
  preu: number;
  kpi: {
    proves: number;
    compres: number;
    conversio: Fraccio;
    venut_sense_provar: number;
    respostes_motiu: number;
    taxa_resposta_motiu: Fraccio;
  };
  talles: TallaModel[];
  motius: MotiuCompte[];
  serie_setmanal: PuntSetmanal[];
  provat_amb: ProvatAmb[];
  origen: Origen | null;
  efecte_origen: Experiment | null;
  /** v0.3 (C): el mateix model en dues talles a la mateixa sessió. */
  dubte_talla?: DubteTallaModel | null;
}

export interface CompraParell { [talla: string]: number }
export interface ParellTalla { model?: string; nom?: string; talles: string; sessions: number; comprada: CompraParell; mostra_petita?: boolean }
export interface DubteTallaModel { sessions: number; sessions_model?: number; mostra_petita?: boolean; pct_sessions_model: Fraccio; talla_mes_comprada: string | null; parells_talla: ParellTalla[] }

// ── GET /talles ──────────────────────────────────────────────────────────
export interface CellaTalla { categoria: string; talla: string; proves: number; compres: number; conversio: Fraccio }

export interface NoQuadra {
  model: string;
  nom: string;
  talla: string;
  conversio: Fraccio;
  conversio_resta_talles: Fraccio;
  text: string;
}

export interface TallaCorba { talla: string; pct_proves: Fraccio; pct_compres: Fraccio; pct_estoc: Fraccio; proposta_pct: Fraccio }
export interface CorbaModel { model: string; nom: string; talles: TallaCorba[] }

export interface Talles { taula: CellaTalla[]; no_quadra: NoQuadra[]; corba: CorbaModel[] }

// ── GET /demanda-perduda ─────────────────────────────────────────────────
export interface VariantPerduda { model: string; nom: string; color: string; talla: string; n: number; estoc: number }
export interface DemandaPerduda { total: number; per_variant: VariantPerduda[]; text: string }

// ── GET /motius ──────────────────────────────────────────────────────────
export interface MotiusModel { model: string; nom: string; respostes: number; motius: Partial<Record<Motiu, number>> }
export interface Motius {
  respostes: number;
  sessions_fitxa: number;
  taxa_resposta: Fraccio;
  per_motiu: MotiuCompte[];
  per_model: MotiusModel[];
}

// ── GET /servei ──────────────────────────────────────────────────────────
export type EstatPeticio = 'pendent' | 'en_cami' | 'lliurada' | 'no_disponible';

export interface CellaOcupacio { dia_setmana: number; hora: number; sessions: number; pct_totes_plenes: Fraccio }

export interface Servei {
  peticions: number;
  /** v0.3 (A.4) */
  peticions_assistencia?: number;
  peticions_per_sessio: number | null;
  mediana_s: number | null;
  pct_sota_90s: Fraccio;
  per_estat: Record<EstatPeticio, number>;
  ocupacio: { durada_mitjana_s: number | null; pct_temps_totes_plenes: Fraccio; mapa: CellaOcupacio[] };
  peces_per_sessio: { peces: number; sessions: number; pct_amb_compra: Fraccio }[];
}

// ── GET /estoc ───────────────────────────────────────────────────────────
export type AccioSuggeriment = 'traspassar' | 'moure_a_sala' | 'promocio' | 'retornar' | 'revisar';
export interface Suggeriment { accio: AccioSuggeriment; text: string; botiga_desti: string | null }
export interface EstocParat {
  gtin: string; model: string; nom: string; talla: string; unitats: number; dies_sense_activitat: number;
  // v0.3 (D)
  color?: string; categoria?: string; botiga_id?: string; valor_eur?: number; dies_parat?: number;
  darrera_prova?: DataHora | null; darrera_venda?: DataHora | null;
  proves_altres_botigues?: number; vendes_altres_botigues?: number;
  suggeriment?: Suggeriment | null; tasca?: Tasca | null;
}
export interface ResumParat { unitats: number; valor_eur: number; per_categoria: { categoria: string; unitats: number; valor_eur: number }[] }
export interface RiscRebaixa { model: string; nom: string; unitats: number; cobertura_setmanes: number | null; conversio: Fraccio; quartil_categoria: number | null }
export interface Estoc {
  parat: EstocParat[];
  risc_rebaixa: RiscRebaixa[];
  precisio: { recomptes: number; error_mitja_pct: Fraccio } | null;
  resum_parat?: ResumParat;
}

// ── GET /fitxa-nfc ───────────────────────────────────────────────────────
export type Seccio = 'origen' | 'talles' | 'cura' | 'preguntes' | 'motiu' | 'peticio_talla';
export interface FitxaNfc {
  tocs: number;
  sessions_cabina: number;
  tocs_per_sessio: number | null;
  seccions: { seccio: Seccio; n: number; pct: Fraccio }[];
  idiomes: { idioma: string; n: number; pct: Fraccio }[];
}

// ── GET /experiments ─────────────────────────────────────────────────────
export interface RespostaExperiments { experiments: Experiment[] }

export interface NouExperiment {
  id: string;
  botiga_id: string;
  variable: string;
  hipotesi: string;
  unitat: string;
  inici: Data;
  setmanes: number;
  proves_minimes: number;
}

// ── GET /alertes ─────────────────────────────────────────────────────────
export type TipusAlerta = 'peticio_talla' | 'talla_esgotada' | 'peca_abandonada' | 'molt_provat_poc_venut';
export interface Alerta {
  id: string;
  tipus: TipusAlerta;
  text: string;
  botiga_id: string;
  cabina: string | null;
  creada: DataHora;
  estat: string;
  ref: number | string | null;
}
export interface RespostaAlertes { alertes: Alerta[] }

/** GET /estat-sistema */
export interface EstatCabina {
  cabina_id: string;
  nom: string;
  botiga_id: string;
  darrera_lectura: DataHora | null;
  darrer_sensor: DataHora | null;
  hores_sense_dades: number | null;
  alerta: boolean;
}
export interface EstatSistema {
  cabines: EstatCabina[];
  darrera_venda: DataHora | null;
  dies_sense_vendes: number | null;
  peces_llegides: number;
  peces_desconegudes: number;
  pct_desconegudes: number | null;
  hores_alerta: number;
  generat: DataHora;
  periode: { des: string; fins: string };
}

// ── GET /valor ───────────────────────────────────────────────────────────
export interface Palanca {
  palanca: string;
  insights: number[];
  formula: string;
  valor_eur: number | null;
  detall: string;
  es_estimacio: boolean;
}
export interface Valor {
  parametres: Record<string, number>;
  llindar_peces_mes: number | null;
  palanques: Palanca[];
}

// ── GET /informes/{tipus} ────────────────────────────────────────────────
export type TipusInforme = 'diari' | 'setmanal' | 'mensual' | 'temporada' | 'pilot' | 'mango';
export interface BlocInforme {
  id: string;
  titol: string;
  text: string;
  /** La forma depèn del bloc; el contracte no la fixa. */
  dades: unknown;
}
export type UnitatGrafic = 'pct' | 'enter' | 'eur' | 'segons';
export type TipusGrafic = 'linia' | 'barres' | 'barres_apilades' | 'donut';
export interface GraficInforme {
  id: string; titol: string; tipus: TipusGrafic; unitat: UnitatGrafic;
  eix_x: string[]; series: { nom: string; valors: (number | null)[] }[]; nota?: string | null;
}
export interface XifraInforme { etiqueta: string; valor: number | null; unitat: UnitatGrafic; variacio?: number | null; vs?: string | null }
export interface Informe {
  tipus: TipusInforme;
  titol: string;
  periode: Periode;
  blocs: BlocInforme[];
  accio: Accio | null;
  avisos: string[];
  /** v0.3 (E.2) */
  grafics?: GraficInforme[];
  xifres?: XifraInforme[];
}

// ── Informes lliurats i programació (E.4) ────────────────────────────────
export type EstatEnviament = 'no_enviat' | 'enviat' | 'error';
export interface InformeLliurat {
  id: number; tipus: TipusInforme; botiga_id: string | null; des: Data; fins: Data; generat: DataHora;
  estat_enviament: EstatEnviament; enviat_a: string[];
}
export interface RespostaLliurats { lliurats: InformeLliurat[] }
export interface Programacio {
  id: number; botiga_id: string | null; tipus: TipusInforme; actiu: boolean;
  dia_setmana: number | null; dia_mes: number | null; data: Data | null; hora: string;
  destinataris: string[]; propera: DataHora | null;
}
export type NovaProgramacio = Omit<Programacio, 'id' | 'propera'>;
export interface RespostaProgramacio { programacions: Programacio[] }

// ── GET /peces/{epc}/historial ───────────────────────────────────────────
export interface HistorialPeca {
  epc: string;
  gtin: string;
  model: string;
  nom: string;
  talla: string;
  esdeveniments: { ts: DataHora; tipus: 'prova' | 'venda' | 'abandonada' | 'nfc'; detall: string }[];
}

// ── GET /perdues ─────────────────────────────────────────────────────────
export interface Perdues { actiu: boolean; per_zona_hora: { cabina: string; hora: number; n: number }[]; total: number }

// ── Operació ─────────────────────────────────────────────────────────────
export type TipusPeticio = 'talla' | 'assistencia';
export interface AltraBotiga { botiga_id: string; nom: string; unitats: number }
export interface Peticio {
  id: number;
  model: string;
  nom: string;
  color: string;
  talla: string;
  cabina: string;
  hora_peticio: DataHora;
  estat: EstatPeticio;
  disponible: boolean;
  segons_espera: number;
  /** v0.3 (A.4): «assistencia» = el client demana que l'atenguin (talla buida). */
  tipus?: TipusPeticio;
  /** v0.3 (A.5): on n'hi ha, quan la talla demanada no hi és. */
  altres_botigues?: AltraBotiga[];
}
export interface RespostaPeticions { peticions: Peticio[] }

export interface Abandonada {
  id: number;
  epc: string;
  model: string;
  nom: string;
  talla: string;
  cabina: string;
  detectada: DataHora;
  resolta: boolean;
}
export interface RespostaAbandonades { abandonades: Abandonada[] }

export type EstatDecisio = 'proposada' | 'acceptada' | 'feta' | 'descartada';
export interface Decisio {
  id: number;
  botiga_id: string | null;
  creada: DataHora;
  titol: string;
  descripcio: string;
  insight: number | string | null;
  model: string | null;
  responsable: string | null;
  data_limit: Data | null;
  estat: EstatDecisio;
  experiment_id: string | null;
  resultat: string | null;
}
export interface RespostaDecisions { decisions: Decisio[] }
export type NovaDecisio = Omit<Decisio, 'id' | 'creada'>;

export interface ResultatImport { importades: number; errors: string[] }

export interface Parametres { botiga_id: string; valors: Record<string, string> }

export interface ResultatShopify { comandes: number; linies: number; estoc: number }

// ── Tasques de botiga (D.1) ──────────────────────────────────────────────
export type TipusTasca = 'traspassar' | 'moure_a_sala' | 'promocio' | 'retornar' | 'recompte' | 'altre';
export type EstatTasca = 'pendent' | 'feta' | 'descartada';
export interface Tasca {
  id: number; botiga_id: string; tipus: TipusTasca | string; titol: string; detall: string | null;
  gtin: string | null; unitats: number | null; botiga_desti: string | null;
  estat: EstatTasca; creada: DataHora; feta: DataHora | null;
}
export type NovaTasca = { botiga_id: string; tipus: TipusTasca; titol: string; detall?: string | null; gtin?: string | null; unitats?: number | null; botiga_desti?: string | null };
export interface RespostaTasques { tasques: Tasca[] }

// ── Provadors en directe (B.1) ───────────────────────────────────────────
export type EstatCabinaDirecte = 'ocupada' | 'lliure' | 'porta_oberta' | 'sense_dades';
export interface PecaCabina { epc: string; model: string; nom: string; talla: string; color: string; des_de: DataHora }
export interface CabinaDirecte {
  cabina_id: string; nom: string; botiga_id: string; estat: EstatCabinaDirecte; des_de: DataHora | null;
  peces: PecaCabina[]; peticions_obertes: number;
  avui: { sessions: number; proves: number; durada_mitjana_s: number | null };
}
export interface ProvadorsDirecte {
  generat: DataHora; cabines: CabinaDirecte[];
  resum: { ocupades: number; lliures: number; sessions_avui: number; proves_avui: number };
}

// ── Sessions (C) ─────────────────────────────────────────────────────────
export interface Sessions {
  kpi: { sessions: number; peces_per_sessio_mitjana: number | null; peces_per_sessio_mediana: number | null; durada_mitjana_s: number | null; pct_sessions_amb_compra: Fraccio };
  per_nombre_peces: { peces: string; sessions: number; amb_compra: number; conversio_sessio: Fraccio; unitats_comprades: number; mostra_petita?: boolean }[];
  provades_juntes: { model_a: string; nom_a: string; model_b: string; nom_b: string; sessions: number; lift: number | null; conversio_conjunta: Fraccio; mostra_petita?: boolean }[];
  mateix_model_diferent_talla: {
    sessions: number; pct_sessions: Fraccio;
    parells_talla: ParellTalla[];
    per_model: { model: string; nom: string; sessions_dubte: number; pct_sessions_model: Fraccio; talla_mes_comprada: string | null; mostra_petita?: boolean }[];
  };
  per_durada: { tram: string; sessions: number; conversio_sessio: Fraccio; mostra_petita?: boolean }[];
  per_hora: { hora: number; sessions: number; conversio_sessio: Fraccio; mostra_petita?: boolean }[];
}

// ── Fitxa NFC configurable (A) ───────────────────────────────────────────
export type SeccioFitxa = 'talles' | 'composicio' | 'origen' | 'cura' | 'combina' | 'faq';
export type MotiuFitxa = 'talla' | 'preu' | 'tall' | 'qualitat' | 'color' | 'nomes_mirava' | 'altre';
export type MostraEstoc = 'no' | 'disponibilitat' | 'unitats';
export interface ConfigFitxa {
  seccions: { ordre: SeccioFitxa[]; visibles: Record<SeccioFitxa, boolean> };
  accions: { demana_talla: boolean; demana_assistencia: boolean; per_que_no: boolean; mostra_estoc: MostraEstoc };
  idiomes: string[];
  textos: { benvinguda?: Record<string, string>; peu?: Record<string, string> };
  'aparença': { color_principal: string; logo_data_url: string | null; nom_marca: string };
  motius: MotiuFitxa[];
}
/** Configuració d'una botiga: només els camps que sobreescriu. */
export interface ConfigFitxaParcial {
  seccions?: Partial<ConfigFitxa['seccions']>;
  accions?: Partial<ConfigFitxa['accions']>;
  idiomes?: string[];
  textos?: ConfigFitxa['textos'];
  'aparença'?: Partial<ConfigFitxa['aparença']>;
  motius?: MotiuFitxa[];
}
export interface RespostaConfigFitxa { general: ConfigFitxa; botiga: ConfigFitxaParcial | null; efectiva: ConfigFitxa }
export interface ModelFitxa { model: string; nom: string; categoria: string; idiomes_amb_contingut: string[]; te_origen: boolean }
export interface ContingutModel {
  nom?: string; descripcio?: string; ajust?: string; cura?: string[]; guia_talles?: string;
  faq?: { q: string; a: string }[]; combina?: string[];
}
export interface DetallModelFitxa { model: string; contingut: Record<string, ContingutModel>; origen: Record<string, unknown> | null }

// ── Integracions (F) ─────────────────────────────────────────────────────
export type Proveidor = 'shopify' | 'square' | 'csv_url';
export type AbastSync = 'cataleg' | 'vendes' | 'estoc';
export interface Integracio {
  id: number; botiga_id: string | null; proveidor: Proveidor; config: Record<string, unknown>; te_secret: boolean;
  actiu: boolean; abast: AbastSync[]; interval_min: number; darrera_sync: DataHora | null;
  estat: 'ok' | 'error' | 'mai'; missatge: string | null;
}
export interface NovaIntegracio { botiga_id: string | null; proveidor: Proveidor; config: Record<string, unknown>; secret?: string | null; abast: AbastSync[]; interval_min: number }
export interface CanviIntegracio { config?: Record<string, unknown>; secret?: string; actiu?: boolean; abast?: AbastSync[]; interval_min?: number; botiga_id?: string | null }
export interface ResultatProvaIntegracio { ok: boolean; detall: { botiga?: string; ubicacions?: { id: string; nom: string }[]; [k: string]: unknown } }
export interface ResumSync { cataleg: number; linies_venda: number; devolucions: number; estoc: number }
export interface RegistreSync { inici: DataHora; fi: DataHora | null; estat: string; resum: Partial<ResumSync> | null; error: string | null }

/** Esdeveniments del flux SSE GET /flux. */
export type EsdevenimentFlux =
  | { tipus: 'peticio'; dades: Peticio }
  | { tipus: 'abandonada'; dades: Abandonada }
  | { tipus: 'alerta'; dades: Alerta }
  | { tipus: 'cabina'; dades: CabinaDirecte }
  | { tipus: 'tasca'; dades: Tasca };
