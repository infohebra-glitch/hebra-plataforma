/**
 * Programació d'informes (docs/ESPECIFICACIO-v3.md, E.1): quan toca la propera
 * generació i com es diu en paraules. Funcions pures (hora local del navegador).
 */
import type { NovaProgramacio, TipusInforme } from '../api/types';
import { DIES_SETMANA_LLARG, dataLocal, diaLlarg } from './format';

export type Recurrencia = 'diari' | 'setmanal' | 'mensual' | 'data';

/** Cada tipus d'informe té una sola manera de programar-se. */
export const recurrencia = (t: TipusInforme): Recurrencia =>
  t === 'diari' ? 'diari' : t === 'setmanal' ? 'setmanal' : t === 'mensual' ? 'mensual' : 'data';

type Prog = Pick<NovaProgramacio, 'tipus' | 'actiu' | 'dia_setmana' | 'dia_mes' | 'data' | 'hora'>;

function ambHora(d: Date, hora: string): Date {
  const [h, m] = hora.split(':').map(Number);
  const r = new Date(d);
  r.setHours(h || 0, m || 0, 0, 0);
  return r;
}

/** Propera execució estrictament posterior a `ara`, o null si ja no n'hi haurà cap. */
export function properaExecucio(p: Prog, ara: Date = new Date()): Date | null {
  if (!p.actiu || !/^\d{1,2}:\d{2}$/.test(p.hora)) return null;
  const r = recurrencia(p.tipus);
  if (r === 'data') {
    if (!p.data) return null;
    const d = ambHora(dataLocal(p.data), p.hora);
    return d > ara ? d : null;
  }
  if (r === 'diari') {
    const d = ambHora(ara, p.hora);
    if (d <= ara) d.setDate(d.getDate() + 1);
    return d;
  }
  if (r === 'setmanal') {
    const objectiu = p.dia_setmana ?? 0; // 0 = dilluns
    const d = ambHora(ara, p.hora);
    const avui = (d.getDay() + 6) % 7;
    let falten = (objectiu - avui + 7) % 7;
    if (falten === 0 && d <= ara) falten = 7;
    d.setDate(d.getDate() + falten);
    return d;
  }
  const dia = Math.min(28, Math.max(1, p.dia_mes ?? 1));
  const d = ambHora(new Date(ara.getFullYear(), ara.getMonth(), dia, 12), p.hora);
  if (d <= ara) d.setMonth(d.getMonth() + 1);
  return d;
}

const periodeCobert: Record<Recurrencia, string> = {
  diari: 'resum del dia anterior', setmanal: 'setmana anterior, de dilluns a diumenge', mensual: 'mes anterior', data: 'una sola vegada',
};

/** «Cada dilluns a les 08:00 · setmana anterior, de dilluns a diumenge» */
export function descriuProgramacio(p: Prog): string {
  const r = recurrencia(p.tipus);
  const h = `a les ${p.hora}`;
  if (r === 'diari') return `Cada dia ${h} · ${periodeCobert.diari}`;
  if (r === 'setmanal') return `Cada ${DIES_SETMANA_LLARG[p.dia_setmana ?? 0]} ${h} · ${periodeCobert.setmanal}`;
  if (r === 'mensual') return `El dia ${p.dia_mes ?? 1} de cada mes ${h} · ${periodeCobert.mensual}`;
  return p.data ? `Una vegada, el ${diaLlarg(p.data)} ${h}` : 'Una vegada (falta la data)';
}

const fDia = new Intl.DateTimeFormat('ca-ES', { weekday: 'long', day: 'numeric', month: 'long' });
const p2 = (n: number) => String(n).padStart(2, '0');

/** «avui a les 08:00», «demà a les 08:00», «dilluns, 9 de novembre a les 08:00». */
export function textPropera(d: Date | string | null, ara: Date = new Date()): string {
  if (!d) return 'No es tornarà a generar';
  const x = typeof d === 'string' ? new Date(d) : d;
  const h = `a les ${p2(x.getHours())}:${p2(x.getMinutes())}`;
  const dies = Math.round((new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime() - new Date(ara.getFullYear(), ara.getMonth(), ara.getDate()).getTime()) / 86400000);
  if (dies === 0) return `avui ${h}`;
  if (dies === 1) return `demà ${h}`;
  return `${fDia.format(x)}${x.getFullYear() !== ara.getFullYear() ? ` del ${x.getFullYear()}` : ''} ${h}`;
}

/** Valida una llista de correus escrita a mà (separats per comes, espais o salts). */
export function llegeixCorreus(text: string): { correus: string[]; dolents: string[] } {
  const parts = text.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);
  const bo = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  return { correus: [...new Set(parts.filter((x) => bo.test(x)))], dolents: parts.filter((x) => !bo.test(x)) };
}
