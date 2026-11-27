/**
 * Mapa de les peces: cada model és un punt amb el seu nom, col·locat segons quantes vegades s'ha provat (x)
 * i quina part d'aquestes proves acaba en compra (y). Les línies de la mitjana parteixen el pla en quatre
 * zones; la de baix a la dreta (molt provat, poc venut) és la que cal mirar i va en grana.
 * És el mateix gràfic que surt a l'informe setmanal i al mensual (hebra/grafics_svg.py, `dispersio`).
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { formatUnitat, sostre } from '../../lib/escala';
import { useAmplada } from '../../lib/useApi';
import { colocaNoms } from './etiquetes';

export interface PuntPeca { clau: string; nom: string; x: number; y: number | null; alerta?: boolean; enllac?: string }

export function Dispersio({ titol, punts, nomX, nomY, alcada = 380 }: {
  titol: string; punts: PuntPeca[]; nomX: string; nomY: string; alcada?: number;
}) {
  const [ref, amplada] = useAmplada<HTMLDivElement>();
  const [actiu, setActiu] = useState<string | null>(null);
  const valids = punts.filter((p) => p.y !== null) as (PuntPeca & { y: number })[];
  const w = Math.max(300, amplada), h = alcada;
  const m = { e: 48, d: 24, s: 24, i: 40 };
  const pw = w - m.e - m.d, ph = h - m.s - m.i;
  // Els eixos no comencen a 0: així les peces no s'amunteguen en un racó.
  const [xmin, xmax, xticks] = interval(valids.map((p) => p.x), 10, 0.8, 1.12, Infinity);
  const [ymin, ymax, yticks] = interval(valids.map((p) => p.y), 0.05, 0.6, 1.2, 1);
  const px = (v: number) => m.e + ((v - xmin) / (xmax - xmin)) * pw;
  const py = (v: number) => m.s + ph - ((v - ymin) / (ymax - ymin)) * ph;
  const mitja = (a: number[]) => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0);
  const mx = mitja(valids.map((p) => p.x)), my = mitja(valids.map((p) => p.y));
  const radi = (p: PuntPeca) => (p.alerta ? 7 : 6);

  // On va el nom de cada punt: mai sobre un altre punt ni sobre un altre nom (etiquetes.ts).
  const zona: [number, number, number, number] = [m.e + pw - 150, m.s + ph - 22, m.e + pw, m.s + ph];
  const caixes = colocaNoms(valids.map((p) => [px(p.x), py(p.y)] as [number, number]),
    valids.map((p) => p.nom.length * 7), [m.e, m.s, m.e + pw, m.s + ph], [zona]);
  const etiquetes: Record<string, { dreta: boolean; ly: number; lx: number }> = {};
  valids.forEach((p, k) => {
    const c = caixes[k];
    etiquetes[p.clau] = { dreta: c.dreta, ly: (c.y0 + c.y1) / 2, lx: c.dreta ? c.x0 + 2 : c.x1 - 2 };
  });

  return (
    <figure className="grafic dispersio" style={{ margin: 0 }} ref={ref}>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
        aria-label={`${titol}. ${valids.map((p) => `${p.nom}: ${p.x} proves, ${formatUnitat(p.y, 'pct')}`).join('; ')}.`}>
        {/* Zona a vigilar: molt provat (dreta de la mitjana), poc venut (sota la mitjana) */}
        <rect x={px(mx)} y={py(my)} width={Math.max(0, m.e + pw - px(mx))} height={Math.max(0, m.s + ph - py(my))} className="zona-alerta" />
        {yticks.map((t) => (
          <g key={`y${t}`}><line x1={m.e} x2={m.e + pw} y1={py(t)} y2={py(t)} className="grid" />
            <text x={m.e - 8} y={py(t)} dy="0.32em" textAnchor="end" className="eix-text">{formatUnitat(t, 'pct')}</text></g>
        ))}
        {xticks.map((t) => (
          <text key={`x${t}`} x={px(t)} y={m.s + ph + 18} textAnchor="middle" className="eix-text">{t}</text>
        ))}
        <line x1={px(mx)} x2={px(mx)} y1={m.s} y2={m.s + ph} className="mitjana" />
        <line x1={m.e} x2={m.e + pw} y1={py(my)} y2={py(my)} className="mitjana" />
        <text x={m.e + pw} y={m.s + ph - 8} textAnchor="end" className="zona-text">Molt provat, poc venut</text>
        <text x={m.e + pw} y={m.s + 12} textAnchor="end" className="zona-text suau">Molt provat i es ven</text>
        <text x={m.e + 8} y={m.s + 12} className="zona-text suau">Poc provat, es ven</text>
        <text x={m.e + pw / 2} y={h - 4} textAnchor="middle" className="eix-nom">{nomX}</text>
        <text x={12} y={m.s + ph / 2} textAnchor="middle" className="eix-nom" transform={`rotate(-90 12 ${m.s + ph / 2})`}>{nomY}</text>
        {[...valids].sort((a, b) => Number(a.alerta) - Number(b.alerta)).map((p) => {
          const r = radi(p), cx = px(p.x), cy = py(p.y), { dreta, ly, lx } = etiquetes[p.clau];
          const apartat = Math.abs(ly - cy) > 4;
          const cos = (
            <g key={p.clau} className={`peca-punt${p.alerta ? ' alerta' : ''}${actiu === p.clau ? ' actiu' : ''}`}
              onPointerEnter={() => setActiu(p.clau)} onPointerLeave={() => setActiu(null)}>
              {apartat && <line x1={cx} y1={cy} x2={dreta ? lx - 2 : lx + 2} y2={ly} className="guia-nom" />}
              <circle cx={cx} cy={cy} r={14} className="diana" />
              <circle cx={cx} cy={cy} r={r} className="cercle" />
              <text x={lx} y={ly} dy="0.32em" textAnchor={dreta ? 'start' : 'end'} className="nom-punt">{p.nom}</text>
              <title>{`${p.nom}: ${p.x} proves, ${formatUnitat(p.y, 'pct')} acaben en compra`}</title>
            </g>
          );
          return p.enllac ? <Link key={p.clau} to={p.enllac} aria-label={p.nom}>{cos}</Link> : cos;
        })}
        {valids.filter((p) => p.clau === actiu).map((p) => (
          <g key="globus" className="globus-svg" pointerEvents="none">
            <rect x={Math.max(m.e, Math.min(px(p.x) - 82, w - 170))} y={py(p.y) - 62} width={164} height={44} rx={4} />
            <text x={Math.max(m.e, Math.min(px(p.x) - 82, w - 170)) + 8} y={py(p.y) - 45}>{p.nom}</text>
            <text x={Math.max(m.e, Math.min(px(p.x) - 82, w - 170)) + 8} y={py(p.y) - 27} className="suau">{p.x} proves · {formatUnitat(p.y, 'pct')} compren</text>
          </g>
        ))}
      </svg>
      <figcaption className="petit muted">Cada punt és un model. Les línies discontínues són la mitjana del període.</figcaption>
    </figure>
  );
}

/** Interval «rodó» que conté els valors amb una mica de marge, i els seus ticks. */
function interval(v: number[], gra: number, baix: number, alt: number, topall: number): [number, number, number[]] {
  if (!v.length) return [0, 1, [0, 1]];
  const lo = Math.max(0, Math.floor((Math.min(...v) * baix) / gra) * gra);
  const hi = Math.min(topall, Math.max(lo + gra, Math.ceil((Math.max(...v) * alt) / gra) * gra));
  const pas = sostre((hi - lo) / 5);
  const t: number[] = [];
  for (let x = Math.ceil(lo / pas) * pas; x <= hi + 1e-9; x += pas) t.push(Number(x.toPrecision(10)));
  return [lo, hi, t];
}
