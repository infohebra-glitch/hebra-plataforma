/**
 * Diferència entre grups amb el seu interval del 95 %, sobre un eix centrat en 0.
 * Si l'interval travessa el 0, a simple vista es veu que encara no està demostrat.
 */
import { punts } from '../../lib/format';
import { useAmplada } from '../../lib/useApi';

export function IntervalConfianca({ diferencia, ic95, esquerra, dreta }: { diferencia: number; ic95: [number, number]; esquerra: string; dreta: string }) {
  const [ref, amplada] = useAmplada<HTMLDivElement>(480);
  const w = Math.max(260, amplada), h = 100, m = 16;
  const abast = Math.max(0.05, Math.abs(ic95[0]), Math.abs(ic95[1]), Math.abs(diferencia)) * 1.15;
  const px = (v: number) => m + ((v + abast) / (2 * abast)) * (w - 2 * m);
  const y = 46;
  const travessa = ic95[0] < 0 && ic95[1] > 0;
  const desc = `Diferència observada ${punts(diferencia, 1)}; interval del 95 % entre ${punts(ic95[0], 1)} i ${punts(ic95[1], 1)}. ${travessa ? 'L’interval inclou el zero: encara no es pot dir quin grup ven més.' : 'L’interval no inclou el zero.'}`;
  return (
    <div ref={ref} className="grafic">
      <svg width={w} height={h} role="img" aria-label={desc}>
        <text x={m} y={14}>← {esquerra}</text>
        <text x={w - m} y={14} textAnchor="end">{dreta} →</text>
        <line className="eix" x1={m} x2={w - m} y1={y} y2={y} />
        <line stroke="var(--fg-2)" strokeWidth={1} x1={px(0)} x2={px(0)} y1={y - 12} y2={y + 12} />
        <text x={px(0)} y={y + 40} textAnchor="middle">0 = cap diferència</text>
        <line className="linia s1" x1={px(ic95[0])} x2={px(ic95[1])} y1={y} y2={y} strokeWidth={6} opacity={0.35} />
        <line className="s1" strokeWidth={2} x1={px(ic95[0])} x2={px(ic95[0])} y1={y - 8} y2={y + 8} />
        <line className="s1" strokeWidth={2} x1={px(ic95[1])} x2={px(ic95[1])} y1={y - 8} y2={y + 8} />
        <circle className="punt f1" cx={px(diferencia)} cy={y} r={6} />
        <text className="etiqueta-directa" x={px(diferencia)} y={y - 14} textAnchor="middle">{punts(diferencia, 1)}</text>
        <text x={px(ic95[0])} y={y + 24} textAnchor={Math.abs(px(ic95[0]) - px(0)) < 50 ? 'end' : 'middle'}>{punts(ic95[0], 1)}</text>
        <text x={px(ic95[1])} y={y + 24} textAnchor={Math.abs(px(ic95[1]) - px(0)) < 50 ? 'start' : 'middle'}>{punts(ic95[1], 1)}</text>
      </svg>
    </div>
  );
}
