/** Selector de període: valors predefinits → des/fins. */
import { isoData } from './format';

export type TipusPeriode = 'aquesta' | 'passada' | 'trenta' | 'personalitzat';

export interface EstatPeriode { tipus: TipusPeriode; des: string; fins: string }

export const NOMS_PERIODE: Record<TipusPeriode, string> = {
  aquesta: 'Aquesta setmana', passada: 'Setmana passada', trenta: 'Darrers 30 dies', personalitzat: 'Personalitzat',
};

function dilluns(d: Date): Date {
  const r = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12);
  const dia = (r.getDay() + 6) % 7; // 0 = dilluns
  r.setDate(r.getDate() - dia);
  return r;
}

const suma = (d: Date, dies: number): Date => { const r = new Date(d); r.setDate(r.getDate() + dies); return r; };

export function calculaPeriode(tipus: Exclude<TipusPeriode, 'personalitzat'>, avui = new Date()): { des: string; fins: string } {
  const a = new Date(avui.getFullYear(), avui.getMonth(), avui.getDate(), 12);
  if (tipus === 'aquesta') return { des: isoData(dilluns(a)), fins: isoData(a) };
  if (tipus === 'passada') { const dl = suma(dilluns(a), -7); return { des: isoData(dl), fins: isoData(suma(dl, 6)) }; }
  return { des: isoData(suma(a, -29)), fins: isoData(a) };
}
