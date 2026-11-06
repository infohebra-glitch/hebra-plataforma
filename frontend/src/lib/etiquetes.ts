/** Noms en català dels codis que retorna l'API. */
import type { EstatDecisio, EstatPeticio, Motiu, Seccio, TipusAlerta, TipusInforme } from '../api/types';

export const MOTIUS: Record<Motiu, string> = {
  talla: 'Talla', tall: 'Tall o patró', preu: 'Preu', color: 'Color', qualitat: 'Qualitat o teixit', nomes_mirava: 'Només mirava', altre: 'Altre',
};
export const motiu = (m: string | null | undefined): string => (m ? MOTIUS[m as Motiu] ?? m : '—');

export const SECCIONS: Record<Seccio, string> = {
  origen: 'Origen', talles: 'Guia de talles', cura: 'Cura de la peça', preguntes: 'Preguntes', motiu: 'Per què no me l’emporto', peticio_talla: 'Demanar una altra talla',
};
export const seccio = (s: string): string => SECCIONS[s as Seccio] ?? s;

const IDIOMES: Record<string, string> = { ca: 'Català', es: 'Castellà', en: 'Anglès', fr: 'Francès', de: 'Alemany', it: 'Italià', pt: 'Portuguès' };
export const idioma = (i: string): string => IDIOMES[i] ?? i.toUpperCase();

export const ESTATS_PETICIO: Record<EstatPeticio, string> = {
  pendent: 'Pendent', en_cami: 'En camí', lliurada: 'Lliurada', no_disponible: 'No n’hi ha',
};

export const ESTATS_DECISIO: Record<EstatDecisio, string> = {
  proposada: 'Proposada', acceptada: 'Acceptada', feta: 'Feta', descartada: 'Descartada',
};

export const TIPUS_ALERTA: Record<TipusAlerta, string> = {
  peticio_talla: 'Petició de talla', talla_esgotada: 'Talla esgotada', peca_abandonada: 'Peça abandonada', molt_provat_poc_venut: 'Molt provat, poc venut',
};

export const INFORMES: { tipus: TipusInforme; nom: string; per: string; descripcio: string }[] = [
  { tipus: 'diari', nom: 'Resum diari', per: 'Botiga', descripcio: 'El dia d’ahir en un cop d’ull: proves, compres, peticions i peces abandonades.' },
  { tipus: 'setmanal', nom: 'Informe setmanal', per: 'Producte i botiga', descripcio: 'Tres xifres, el que es prova i no es ven, la talla que no quadra, la demanda perduda, els motius i l’acció de la setmana.' },
  { tipus: 'mensual', nom: 'Informe mensual d’accions', per: 'Direcció i producte', descripcio: 'Decisions amb resultat, conversió per categoria i talla, corba de talles, estoc parat, fitxa NFC, prova en curs i valor estimat.' },
  { tipus: 'temporada', nom: 'Fi de temporada', per: 'Producte i disseny', descripcio: 'Rànquing per família i model, feedback de disseny, corba recomanada, efecte de l’origen i unitats per país.' },
  { tipus: 'pilot', nom: 'Final del pilot', per: 'Direcció', descripcio: 'Criteris d’èxit, qualitat de la dada, proves contra compra, decisions, precisió d’estoc i què no podem afirmar.' },
  { tipus: 'mango', nom: 'Pilot de Mango', per: 'Mango', descripcio: 'Els KPI del dossier i «l’últim metre de l’origen».' },
];

/** Els 25 insights (docs/ESPECIFICACIO.md), per enllaçar decisions i palanques. */
export const INSIGHTS: Record<number, string> = {
  1: 'Proves', 2: 'Conversió de provador', 3: 'Molt provat, poc venut', 4: 'Venut sense provar', 5: 'Talles provades contra comprades',
  6: 'Conversió per talla', 7: 'Demanda perduda', 8: 'Motiu de no compra', 9: 'Peticions de talla', 10: 'Temps de resposta',
  11: 'Ocupació i cicles', 12: 'Peces per sessió', 13: 'Peces abandonades', 14: 'Estoc parat', 15: 'Risc de rebaixa',
  16: 'Ús de la fitxa NFC', 17: 'Efecte de l’origen', 18: 'Efecte de qualsevol canvi', 19: '«Combina amb» mesurat', 20: 'Venda recuperada en línia',
  21: 'Idioma del client', 22: 'Feedback de disseny', 23: 'Precisió d’estoc de la zona', 24: 'Historial de la peça', 25: 'Senyals de pèrdua',
};
/** Claus de text que fa servir el servidor (`decisio.insight`, `Accio.insight`) → número d'insight. */
const CLAUS_INSIGHT: Record<string, number> = {
  molt_provat_poc_venut: 3, venut_sense_provar: 4, corba_talles: 5, talla_no_quadra: 6, demanda_perduda: 7,
  motius: 8, servei: 10, ocupacio: 11, peces_abandonades: 13, estoc_parat: 14, risc_rebaixa: 15,
  fitxa_nfc: 16, experiment: 17, origen: 17, precisio_estoc: 23,
};
const ALTRES_CLAUS: Record<string, string> = { qualitat_dada: 'Qualitat de la dada' };

/** Accepta el número d'insight o la clau de text del servidor. */
export const insight = (n: number | string | null | undefined): string => {
  if (n === null || n === undefined || n === '') return '—';
  const num = typeof n === 'number' ? n : /^\d+$/.test(n) ? Number(n) : CLAUS_INSIGHT[n];
  if (num) return `${num}. ${INSIGHTS[num] ?? ''}`;
  return ALTRES_CLAUS[n as string] ?? String(n).replace(/_/g, ' ');
};

/** Mínim de proves per grup per no marcar «Mostra petita». */
export const MOSTRA_MINIMA = 30;
