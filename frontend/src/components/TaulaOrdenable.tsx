/** Taula amb columnes ordenables (clic o teclat a la capçalera; aria-sort). */
import { useMemo, useState, type ReactNode } from 'react';

export interface Columna<T> {
  clau: string;
  cap: string;
  n?: boolean;
  ordre?: (r: T) => number | string | null;
  cel: (r: T) => ReactNode;
}

export function TaulaOrdenable<T>({ files, columnes, clauFila, titol, ordreInicial, enClic }: {
  files: T[]; columnes: Columna<T>[]; clauFila: (r: T) => string; titol: string;
  ordreInicial?: { clau: string; desc: boolean }; enClic?: (r: T) => void;
}) {
  const [ordre, setOrdre] = useState(ordreInicial ?? { clau: columnes[0].clau, desc: false });
  const ordenades = useMemo(() => {
    const c = columnes.find((x) => x.clau === ordre.clau);
    if (!c?.ordre) return files;
    const f = c.ordre;
    return [...files].sort((a, b) => {
      const va = f(a), vb = f(b);
      if (va === vb) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      const r = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb), 'ca');
      return ordre.desc ? -r : r;
    });
  }, [files, columnes, ordre]);

  return (
    <div className="taula-wrap">
      <table>
        <caption className="sr-only">{titol}. Fes clic a una capçalera per ordenar.</caption>
        <thead>
          <tr>
            {columnes.map((c) => {
              const actiu = ordre.clau === c.clau;
              return (
                <th key={c.clau} scope="col" className={c.n ? 'n' : undefined} aria-sort={actiu ? (ordre.desc ? 'descending' : 'ascending') : undefined}>
                  {c.ordre ? (
                    <button type="button" className="ordena" onClick={() => setOrdre({ clau: c.clau, desc: actiu ? !ordre.desc : !!c.n })}>
                      {c.cap}<span aria-hidden="true">{actiu ? (ordre.desc ? '↓' : '↑') : ''}</span>
                    </button>
                  ) : c.cap}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {ordenades.map((r) => (
            <tr key={clauFila(r)} className={enClic ? 'clicable' : undefined} onClick={enClic ? (e) => { if (!(e.target as HTMLElement).closest('a,button')) enClic(r); } : undefined}>
              {columnes.map((c) => <td key={c.clau} className={c.n ? 'n' : undefined}>{c.cel(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
