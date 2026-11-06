/**
 * Gràfic de línies en SVG (una sola escala Y). Línies de 2 px, punts amb
 * anell de superfície, etiqueta directa al final, creu que segueix el punter
 * (i les fletxes del teclat) i, sempre, la mateixa informació en una taula.
 * Opcionalment marca dies amb una banda de fons (p. ex. dies «amb origen»).
 */
import { useState, type KeyboardEvent, type PointerEvent } from 'react';
import { useAmplada } from '../../lib/useApi';

export interface Serie { clau: string; nom: string; classe: 's1' | 's2'; valors: (number | null)[] }

interface Props {
  titol: string;
  x: string[];
  etiquetaX: (i: number) => string;
  detallX?: (i: number) => string;
  series: Serie[];
  formatY: (n: number) => string;
  /** Format del valor al globus i a la taula (per defecte, formatY). */
  formatValor?: (n: number | null, serie: Serie, i: number) => string;
  bandes?: boolean[];
  nomBanda?: string;
  maxY?: number;
  alcada?: number;
}

function sostre(n: number): number {
  if (n <= 0) return 1;
  const pot = 10 ** Math.floor(Math.log10(n));
  const r = n / pot;
  const pas = r <= 1 ? 1 : r <= 2 ? 2 : r <= 2.5 ? 2.5 : r <= 5 ? 5 : 10;
  return pas * pot;
}

export function SerieTemporal({ titol, x, etiquetaX, detallX = etiquetaX, series, formatY, formatValor, bandes, nomBanda, maxY, alcada = 240 }: Props) {
  const [ref, amplada] = useAmplada<HTMLDivElement>();
  const [actiu, setActiu] = useState<number | null>(null);
  const fv = formatValor ?? ((n: number | null) => (n === null ? '—' : formatY(n)));

  const m = { e: 44, d: 64, s: 12, i: 28 };
  const w = Math.max(280, amplada);
  const h = alcada;
  const pw = w - m.e - m.d, ph = h - m.s - m.i;
  const n = x.length;
  const tots = series.flatMap((s) => s.valors.filter((v): v is number => v !== null));
  const ymax = maxY ?? sostre(Math.max(0, ...tots) * 1.08);
  const pas = n > 1 ? pw / (n - 1) : 0;
  const px = (i: number) => m.e + (n > 1 ? i * pas : pw / 2);
  const py = (v: number) => m.s + ph - (v / ymax) * ph;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * ymax);
  const cadaX = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(pw / 64))));

  const cami = (s: Serie) => {
    let d = '';
    s.valors.forEach((v, i) => { if (v === null) return; d += `${d && s.valors[i - 1] !== null ? 'L' : 'M'}${px(i).toFixed(1)},${py(v).toFixed(1)}`; });
    return d;
  };

  // Etiquetes directes al final, només si no es trepitgen (si no, ja hi ha la llegenda).
  const finals = series.map((s) => {
    let i = s.valors.length - 1;
    while (i >= 0 && s.valors[i] === null) i--;
    return i >= 0 ? { s, i, y: py(s.valors[i] as number) } : null;
  });
  const xoquen = finals.length === 2 && finals[0] && finals[1] && Math.abs(finals[0].y - finals[1].y) < 16;

  const mou = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const rx = ((e.clientX - r.left) / r.width) * pw;
    setActiu(Math.max(0, Math.min(n - 1, n > 1 ? Math.round(rx / pas) : 0)));
  };
  const tecla = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === 'ArrowRight') { setActiu((a) => Math.min(n - 1, (a ?? -1) + 1)); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { setActiu((a) => Math.max(0, (a ?? n) - 1)); e.preventDefault(); }
    if (e.key === 'Escape') setActiu(null);
  };

  const globusEsquerra = actiu !== null && px(actiu) > w * 0.6;

  return (
    <figure className="grafic" style={{ margin: 0 }}>
      <ul className="llegenda">
        {series.map((s) => <li key={s.clau}><span className={`clau-linia bg-${s.classe}`} aria-hidden="true" />{s.nom}</li>)}
        {bandes?.some(Boolean) && nomBanda && <li><span className="clau-banda" aria-hidden="true" />{nomBanda}</li>}
      </ul>
      <div ref={ref} style={{ position: 'relative' }}>
        <svg width={w} height={h} role="img" aria-label={`${titol}. Fes servir les fletxes per recórrer els dies; les dades també són a la taula de sota.`} tabIndex={0} onKeyDown={tecla} onBlur={() => setActiu(null)}>
          {bandes?.map((b, i) => {
            if (!b) return null;
            const x0 = Math.max(m.e, px(i) - (n > 1 ? pas / 2 : pw / 2));
            const x1 = Math.min(w - m.d, px(i) + (n > 1 ? pas / 2 : pw / 2));
            return <rect key={`b${i}`} className="banda" x={x0} y={m.s} width={Math.max(0, x1 - x0)} height={ph} />;
          })}
          {ticks.map((t) => (
            <g key={t}>
              <line className={t === 0 ? 'eix' : 'grid'} x1={m.e} x2={w - m.d} y1={py(t)} y2={py(t)} />
              <text x={m.e - 8} y={py(t)} dy="0.32em" textAnchor="end">{formatY(t)}</text>
            </g>
          ))}
          {x.map((_, i) => (i % cadaX === 0 || i === n - 1) && (n - 1 - i >= cadaX / 2 || i === n - 1) && (
            <text key={`x${i}`} x={px(i)} y={h - 8} textAnchor="middle">{etiquetaX(i)}</text>
          ))}
          {series.map((s) => <path key={s.clau} className={`linia ${s.classe}`} d={cami(s)} />)}
          {finals.map((f) => f && (
            <g key={`f${f.s.clau}`}>
              <circle className={`punt f${f.s.classe.slice(1)}`} cx={px(f.i)} cy={f.y} r={4} />
              {!xoquen && <text className="etiqueta-directa" x={px(f.i) + 8} y={f.y} dy="0.32em">{formatY(f.s.valors[f.i] as number)}</text>}
            </g>
          ))}
          {actiu !== null && (
            <g>
              <line className="creu" x1={px(actiu)} x2={px(actiu)} y1={m.s} y2={m.s + ph} />
              {series.map((s) => s.valors[actiu] !== null && (
                <circle key={s.clau} className={`punt f${s.classe.slice(1)}`} cx={px(actiu)} cy={py(s.valors[actiu] as number)} r={4.5} />
              ))}
            </g>
          )}
          <rect x={m.e - pas / 2} y={m.s} width={pw + pas} height={ph} fill="transparent" onPointerMove={mou} onPointerLeave={() => setActiu(null)} />
        </svg>
        {actiu !== null && (
          <div className="globus" style={{ top: 8, left: globusEsquerra ? undefined : px(actiu) + 12, right: globusEsquerra ? w - px(actiu) + 12 : undefined }} aria-live="polite">
            <div className="titol-globus">{detallX(actiu)}{bandes?.[actiu] && nomBanda ? ` · ${nomBanda.toLowerCase()}` : ''}</div>
            {series.map((s) => (
              <div key={s.clau} className="fila-globus"><span className={`clau-linia bg-${s.classe}`} aria-hidden="true" /><b>{fv(s.valors[actiu], s, actiu)}</b><span className="nom">{s.nom}</span></div>
            ))}
          </div>
        )}
      </div>
      <details className="veure-taula">
        <summary>Veure les dades en una taula</summary>
        <div className="taula-wrap">
          <table>
            <caption>{titol}</caption>
            <thead><tr><th scope="col">Dia</th>{series.map((s) => <th key={s.clau} scope="col" className="n">{s.nom}</th>)}{nomBanda && bandes && <th scope="col">{nomBanda}</th>}</tr></thead>
            <tbody>
              {x.map((_, i) => (
                <tr key={i}><th scope="row" style={{ textTransform: 'none', letterSpacing: 0, color: 'var(--fg)', fontWeight: 500 }}>{detallX(i)}</th>
                  {series.map((s) => <td key={s.clau} className="n">{fv(s.valors[i], s, i)}</td>)}
                  {nomBanda && bandes && <td>{bandes[i] ? 'Sí' : 'No'}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
