/**
 * Donut (parts d'un total): com a molt 5 porcions amb color i la resta agrupada
 * a «Altres» en gris. Cada porció porta valor i % a la llegenda: el color no és mai l'única pista.
 */
import { useState } from 'react';
import type { UnitatGrafic } from '../../api/types';
import { formatUnitat } from '../../lib/escala';
import { pct } from '../../lib/format';
import { TaulaDades } from './Columnes';

const COLORS = ['var(--serie-1)', 'var(--serie-2)', 'var(--serie-3)', 'color-mix(in oklab, var(--serie-1) 50%, var(--surface))', 'color-mix(in oklab, var(--serie-2) 50%, var(--surface))'];

export function Donut({ titol, etiquetes, valors, unitat = 'enter' }: { titol: string; etiquetes: string[]; valors: (number | null)[]; unitat?: UnitatGrafic }) {
  const [actiu, setActiu] = useState<number | null>(null);
  let parts = etiquetes.map((e, i) => ({ e, v: Math.max(0, valors[i] ?? 0) })).filter((p) => p.v > 0).sort((a, b) => b.v - a.v);
  if (parts.length > 6) parts = [...parts.slice(0, 5), { e: 'Altres', v: parts.slice(5).reduce((s, p) => s + p.v, 0) }];
  const total = parts.reduce((s, p) => s + p.v, 0);
  const r = 62, gruix = 22, c = 2 * Math.PI * r;
  let acumulat = 0;
  const color = (i: number, e: string) => (e === 'Altres' ? 'var(--serie-neutra)' : COLORS[i % COLORS.length]);
  return (
    <figure className="grafic donut" style={{ margin: 0 }}>
      <div className="donut-cos">
        <svg width={160} height={160} viewBox="0 0 160 160" role="img" aria-label={`${titol}: ${parts.map((p) => `${p.e} ${pct(total ? p.v / total : null)}`).join(', ')}.`}>
          <g transform="rotate(-90 80 80)">
            {total > 0 ? parts.map((p, i) => {
              const llarg = (p.v / total) * c;
              const el = <circle key={p.e} cx={80} cy={80} r={r} fill="none" stroke={color(i, p.e)} strokeWidth={actiu === i ? gruix + 4 : gruix}
                strokeDasharray={`${Math.max(0, llarg - 2)} ${c}`} strokeDashoffset={-acumulat} onPointerEnter={() => setActiu(i)} onPointerLeave={() => setActiu(null)} />;
              acumulat += llarg;
              return el;
            }) : <circle cx={80} cy={80} r={r} fill="none" stroke="var(--line-2)" strokeWidth={gruix} />}
          </g>
          <text x={80} y={76} textAnchor="middle" className="donut-total">{formatUnitat(actiu !== null ? parts[actiu].v : total, unitat)}</text>
          <text x={80} y={94} textAnchor="middle">{actiu !== null ? parts[actiu].e : 'en total'}</text>
        </svg>
        <ul className="llegenda-donut">
          {parts.map((p, i) => (
            <li key={p.e} onPointerEnter={() => setActiu(i)} onPointerLeave={() => setActiu(null)}>
              <span className="clau-quadre" style={{ background: color(i, p.e) }} aria-hidden="true" />
              <span className="nom">{p.e}</span>
              <span className="valor">{formatUnitat(p.v, unitat)} · {pct(total ? p.v / total : null)}</span>
            </li>
          ))}
        </ul>
      </div>
      <TaulaDades titol={titol} cap="Part" x={parts.map((p) => p.e)} series={[{ nom: 'Valor', valors: parts.map((p) => p.v) }]} fmt={(v) => formatUnitat(v, unitat)} />
    </figure>
  );
}
