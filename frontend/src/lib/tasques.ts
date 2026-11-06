/** Tasques de botiga (D.1): noms en català i com es fa una tasca a partir d'un suggeriment d'estoc parat. */
import type { AccioSuggeriment, EstocParat, NovaTasca, TipusTasca } from '../api/types';

export const NOMS_TIPUS_TASCA: Record<TipusTasca, string> = {
  traspassar: 'Traspassar', moure_a_sala: 'Treure a la sala', promocio: 'Promoció', retornar: 'Retornar', revisar: 'Revisar', recompte: 'Recompte', altre: 'Altre',
};
export const nomTipusTasca = (t: string) => NOMS_TIPUS_TASCA[t as TipusTasca] ?? t;

export const NOMS_ACCIO: Record<AccioSuggeriment, string> = {
  traspassar: 'Traspassar', moure_a_sala: 'Treure a la sala', promocio: 'Promoció', retornar: 'Retornar', revisar: 'Revisar',
};

export function tascaDeParat(p: EstocParat, botigaPerDefecte: string, nomDesti?: string): NovaTasca {
  const s = p.suggeriment;
  const tipus: TipusTasca = s ? s.accio : 'altre';
  const u = p.unitats === 1 ? '1 unitat' : `${p.unitats} unitats`;
  const que = `${p.nom.toLowerCase()} (${p.talla})`;
  const titol = {
    traspassar: `Traspassar ${u} de ${que}${nomDesti ? ` a ${nomDesti}` : ''}`,
    moure_a_sala: `Treure a la sala ${que}`,
    promocio: `Posar en promoció ${que}`,
    retornar: `Retornar ${u} de ${que} al magatzem`,
    revisar: `Revisar ${que}`,
    recompte: `Recomptar ${que}`,
    altre: `Revisar ${que}`,
  }[tipus];
  return {
    botiga_id: p.botiga_id ?? botigaPerDefecte, tipus, titol: titol.charAt(0).toUpperCase() + titol.slice(1),
    detall: s?.text ?? null, gtin: p.gtin, unitats: p.unitats, botiga_desti: s?.botiga_desti ?? null,
  };
}
