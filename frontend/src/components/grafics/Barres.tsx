/**
 * Barres horitzontals en HTML (motius, seccions, idiomes...). Una sola sèrie,
 * un sol color; cada barra porta el seu valor escrit, així no cal globus.
 */
import { enter, pct } from '../../lib/format';

export interface Barra { clau: string; etiqueta: string; n: number; pct?: number | null }

export function Barres({ items, titol, max, fmt = enter }: { items: Barra[]; titol: string; max?: number; fmt?: (n: number) => string }) {
  const m = max ?? Math.max(1, ...items.map((x) => x.n));
  return (
    <ul className="barres" aria-label={titol}>
      {items.map((x) => (
        <li key={x.clau}>
          <span>{x.etiqueta}</span>
          <span className="pista" aria-hidden="true"><span className="ple" style={{ width: `${(x.n / m) * 100}%`, display: 'block' }} /></span>
          <span className="valor">{fmt(x.n)}{x.pct !== undefined && <small> · {pct(x.pct)}</small>}</span>
        </li>
      ))}
    </ul>
  );
}
