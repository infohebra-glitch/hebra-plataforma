/**
 * Columnes verticals en SVG: una sèrie, diverses agrupades o apilades, sempre amb
 * una sola escala (una sola unitat). Globus amb el punter o les fletxes del teclat,
 * subetiqueta opcional sota cada columna (p. ex. «41 % amb compra») i la taula de dades a sota.
 */
import { useState, type KeyboardEvent } from 'react';
import type { UnitatGrafic } from '../../api/types';
import { formatUnitat, maxEix, ticks } from '../../lib/escala';
import { useAmplada } from '../../lib/useApi';

export interface SerieColumnes { nom: string; valors: (number | null)[] }
const CLASSES = ['f1', 'f2', 'f3'];
const BG = ['bg-s1', 'bg-s2', 'bg-s3'];

export function Columnes({ titol, x, series, unitat = 'enter', apilades = false, subetiquetes, nomEixX = 'Categoria', alcada = 220, destaca }: {
  titol: string; x: string[]; series: SerieColumnes[]; unitat?: UnitatGrafic; apilades?: boolean;
  subetiquetes?: string[]; nomEixX?: string; alcada?: number; destaca?: (i: number) => boolean;
}) {
  const [ref, amplada] = useAmplada<HTMLDivElement>();
  const [actiu, setActiu] = useState<number | null>(null);
  const n = x.length;
  const m = { e: 46, d: 8, s: 16, i: subetiquetes ? 40 : 24 };
  const w = Math.max(260, amplada), h = alcada;
  const pw = w - m.e - m.d, ph = h - m.s - m.i;
  const totals = x.map((_, i) => series.reduce((s, se) => s + (se.valors[i] ?? 0), 0));
  const ymax = maxEix(apilades ? totals : series.flatMap((s) => s.valors), unitat);
  const py = (v: number) => m.s + ph - (v / ymax) * ph;
  const banda = n ? pw / n : pw;
  const ampleGrup = Math.min(banda * 0.7, apilades ? 44 : 22 * series.length + 2 * (series.length - 1));
  const ampleCol = apilades ? ampleGrup : (ampleGrup - 2 * (series.length - 1)) / series.length;
  const fmt = (v: number | null) => formatUnitat(v, unitat);
  const directes = series.length === 1 && banda > 34;

  const tecla = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === 'ArrowRight') { setActiu((a) => Math.min(n - 1, (a ?? -1) + 1)); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { setActiu((a) => Math.max(0, (a ?? n) - 1)); e.preventDefault(); }
    if (e.key === 'Escape') setActiu(null);
  };

  return (
    <figure className="grafic" style={{ margin: 0 }}>
      {series.length > 1 && (
        <ul className="llegenda">{series.map((s, k) => <li key={s.nom}><span className={`clau-quadre ${BG[k % 3]}`} aria-hidden="true" />{s.nom}</li>)}</ul>
      )}
      <div ref={ref} style={{ position: 'relative' }}>
        <svg width={w} height={h} role="img" tabIndex={0} onKeyDown={tecla} onBlur={() => setActiu(null)}
          aria-label={`${titol}. Fes servir les fletxes per recórrer les columnes; les dades també són a la taula de sota.`}>
          {ticks(ymax).map((t) => (
            <g key={t}>
              <line className={t === 0 ? 'eix' : 'grid'} x1={m.e} x2={w - m.d} y1={py(t)} y2={py(t)} />
              <text x={m.e - 8} y={py(t)} dy="0.32em" textAnchor="end">{fmt(t)}</text>
            </g>
          ))}
          {x.map((etq, i) => {
            const cx = m.e + banda * i + banda / 2;
            let acumulat = 0;
            const opac = actiu === null || actiu === i ? 1 : 0.45;
            return (
              <g key={etq + i} onPointerEnter={() => setActiu(i)} onPointerLeave={() => setActiu(null)} opacity={opac}>
                <rect x={m.e + banda * i} y={m.s} width={banda} height={ph} fill="transparent" />
                {series.map((s, k) => {
                  const v = s.valors[i];
                  if (v === null || v === undefined || v <= 0) return null;
                  if (apilades) {
                    const y0 = py(acumulat), y1 = py(acumulat + v);
                    acumulat += v;
                    return <rect key={s.nom} className={CLASSES[k % 3]} x={cx - ampleCol / 2} y={y1} width={ampleCol} height={Math.max(0, y0 - y1 - (k < series.length - 1 ? 0 : 0))} stroke="var(--surface)" strokeWidth={1} />;
                  }
                  const x0 = cx - ampleGrup / 2 + k * (ampleCol + 2);
                  return <rect key={s.nom} className={CLASSES[k % 3]} x={x0} y={py(v)} width={ampleCol} height={Math.max(1, py(0) - py(v))} rx={3} />;
                })}
                {directes && series[0].valors[i] !== null && (
                  <text className={`etiqueta-directa${destaca?.(i) ? ' fort' : ''}`} x={cx} y={py(series[0].valors[i] as number) - 5} textAnchor="middle">{fmt(series[0].valors[i])}</text>
                )}
                <text x={cx} y={h - m.i + 16} textAnchor="middle" className="etiqueta-x">{etq}</text>
                {subetiquetes && <text x={cx} y={h - m.i + 31} textAnchor="middle" className="subetiqueta">{subetiquetes[i]}</text>}
              </g>
            );
          })}
        </svg>
        {actiu !== null && (
          <div className="globus" style={{ top: 4, left: Math.min(w - 170, Math.max(0, m.e + banda * actiu + banda / 2 + 12)) }} aria-live="polite">
            <div className="titol-globus">{nomEixX}: {x[actiu]}</div>
            {series.map((s, k) => (
              <div key={s.nom} className="fila-globus"><span className={`clau-linia ${BG[k % 3]}`} aria-hidden="true" /><b>{fmt(s.valors[actiu])}</b><span className="nom">{s.nom}</span></div>
            ))}
            {apilades && <div className="fila-globus"><b>{fmt(totals[actiu])}</b><span className="nom">en total</span></div>}
            {subetiquetes && <div className="fila-globus"><span className="nom">{subetiquetes[actiu]}</span></div>}
          </div>
        )}
      </div>
      <TaulaDades titol={titol} cap={nomEixX} x={x} series={series} fmt={fmt} extra={subetiquetes} />
    </figure>
  );
}

export function TaulaDades({ titol, cap, x, series, fmt, extra }: { titol: string; cap: string; x: string[]; series: SerieColumnes[]; fmt: (v: number | null) => string; extra?: string[] }) {
  return (
    <details className="veure-taula">
      <summary>Veure les dades en una taula</summary>
      <div className="taula-wrap">
        <table>
          <caption>{titol}</caption>
          <thead><tr><th scope="col">{cap}</th>{series.map((s) => <th key={s.nom} scope="col" className="n">{s.nom}</th>)}{extra && <th scope="col">Nota</th>}</tr></thead>
          <tbody>{x.map((etq, i) => (
            <tr key={etq + i}><th scope="row" className="fila-cap">{etq}</th>{series.map((s) => <td key={s.nom} className="n">{fmt(s.valors[i])}</td>)}{extra && <td>{extra[i]}</td>}</tr>
          ))}</tbody>
        </table>
      </div>
    </details>
  );
}
