/**
 * Mapa de calor com a taula: cada cel·la porta el seu número i un fons d'una
 * sola tonalitat (verd) en 5 graons. La taula és alhora el gràfic i l'alternativa textual.
 */
import type { ReactNode } from 'react';

export interface Cel { v: number | null; text: ReactNode; titol?: string }

export function graoDe(v: number | null, max: number): number {
  if (v === null || max <= 0) return 0;
  const t = v / max;
  if (t <= 0) return 0;
  return Math.min(5, 1 + Math.floor(t * 5 - 1e-9));
}

export function MapaCalor({ titol, files, columnes, cel, max, llegendaEscala, capFila = '' }: {
  titol: string; files: { clau: string; nom: ReactNode }[]; columnes: { clau: string; nom: string }[];
  cel: (fila: string, col: string) => Cel; max?: number; llegendaEscala: [string, string]; capFila?: string;
}) {
  const valors = files.flatMap((f) => columnes.map((c) => cel(f.clau, c.clau).v)).filter((v): v is number => v !== null);
  const m = max ?? Math.max(0, ...valors);
  return (
    <div>
      <div className="taula-wrap">
        <table className="mapa-calor">
          <caption className="sr-only">{titol}</caption>
          <thead><tr><th scope="col">{capFila}</th>{columnes.map((c) => <th key={c.clau} scope="col" style={{ textAlign: 'center' }}>{c.nom}</th>)}</tr></thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.clau}>
                <th scope="row">{f.nom}</th>
                {columnes.map((c) => {
                  const x = cel(f.clau, c.clau);
                  return <td key={c.clau} className="cel" title={x.titol}><span className={`c${graoDe(x.v, m)}`}>{x.text}</span></td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="escala" aria-hidden="true" style={{ marginTop: 8 }}>
        <span style={{ marginRight: 6 }}>{llegendaEscala[0]}</span>
        {[1, 2, 3, 4, 5].map((g) => <span key={g} className={`mostra c${g}`} />)}
        <span style={{ marginLeft: 6 }}>{llegendaEscala[1]}</span>
      </div>
    </div>
  );
}
