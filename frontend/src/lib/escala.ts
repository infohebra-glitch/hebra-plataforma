/** Escales dels gràfics SVG: sostre «rodó» i ticks. Pures, per poder-les provar. */
import type { UnitatGrafic } from '../api/types';
import { enter, eur, pct, segons } from './format';

/** El primer valor «rodó» (1, 2, 2,5, 5 × 10ⁿ) que és ≥ n. */
export function sostre(n: number): number {
  if (!(n > 0)) return 1;
  const pot = 10 ** Math.floor(Math.log10(n));
  const r = n / pot;
  const pas = r <= 1 ? 1 : r <= 2 ? 2 : r <= 2.5 ? 2.5 : r <= 5 ? 5 : 10;
  return Number((pas * pot).toPrecision(12));
}

/** Màxim de l'eix Y: per a fraccions, mai més d'1 (100 %). */
export function maxEix(valors: (number | null | undefined)[], unitat?: UnitatGrafic): number {
  const m = Math.max(0, ...valors.filter((v): v is number => typeof v === 'number' && Number.isFinite(v)));
  const s = sostre(m * 1.08);
  return unitat === 'pct' ? Math.min(1, s) || 1 : s;
}

/** Ticks de 0 a max amb un pas «rodó» (4 trams si es pot; si no, 5 o 2). */
export function ticks(max: number, n?: number): number[] {
  const rodo = (x: number) => { const p = 10 ** Math.floor(Math.log10(x)); return Number.isInteger(Number((x / p).toPrecision(6)) * 2); };
  const trams = n ?? [4, 5, 2].find((k) => rodo(max / k)) ?? 4;
  return Array.from({ length: trams + 1 }, (_, i) => Number(((max * i) / trams).toPrecision(12)));
}

export function formatUnitat(v: number | null | undefined, u: UnitatGrafic): string {
  if (u === 'pct') return pct(v);
  if (u === 'eur') return eur(v);
  if (u === 'segons') return segons(v);
  return enter(v);
}

/** El lift en paraules: quantes vegades més (o menys) del que tocaria per casualitat. */
export function liftEnParaules(lift: number | null | undefined): string {
  if (lift === null || lift === undefined || !Number.isFinite(lift)) return 'Encara no es pot calcular.';
  const x = lift.toLocaleString('ca-ES', { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  if (lift >= 1.15) return `Es proven juntes ${x} vegades més del que tocaria per casualitat.`;
  if (lift <= 0.85) return `Es proven juntes menys del que tocaria per casualitat (${x}).`;
  return `Es proven juntes més o menys com tocaria per casualitat (${x}).`;
}
