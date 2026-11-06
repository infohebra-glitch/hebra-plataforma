/**
 * Corba de talles: per a cada talla, % de les proves (verd) contra % de les
 * compres (coure) i, si n'hi ha, la proposta per a la propera comanda (contorn).
 * Columnes d'un màxim de 22 px, amb 2 px d'aire; globus en passar-hi o en enfocar-hi.
 */
import { useState } from 'react';
import { pct } from '../../lib/format';

export interface FilaCorba { talla: string; pct_proves: number | null; pct_compres: number | null; proposta_pct?: number | null; pct_estoc?: number | null; nota?: string }

export function CorbaTalles({ files, titol }: { files: FilaCorba[]; titol: string }) {
  const [actiu, setActiu] = useState<number | null>(null);
  const ambProposta = files.some((f) => f.proposta_pct != null);
  const max = Math.max(0.05, ...files.flatMap((f) => [f.pct_proves ?? 0, f.pct_compres ?? 0, f.proposta_pct ?? 0]));
  const alt = (v: number | null | undefined) => `${((v ?? 0) / max) * 100}%`;
  return (
    <figure style={{ margin: 0 }}>
      <ul className="llegenda">
        <li><span className="clau-quadre bg-s1" aria-hidden="true" />% de les proves</li>
        <li><span className="clau-quadre bg-s2" aria-hidden="true" />% de les compres</li>
        {ambProposta && <li><span className="clau-quadre" style={{ border: '2px solid var(--fg-2)' }} aria-hidden="true" />Proposta de corba</li>}
      </ul>
      <div style={{ position: 'relative' }} role="group" aria-label={`${titol}. Els valors són a la taula de sota.`}>
        <div className="columnes" style={{ gridTemplateColumns: `repeat(${files.length}, 1fr)` }}>
          {files.map((f, i) => (
            <div key={f.talla} className="columna-grup" tabIndex={0} aria-label={`Talla ${f.talla}: ${pct(f.pct_proves)} de les proves, ${pct(f.pct_compres)} de les compres${ambProposta ? `, proposta ${pct(f.proposta_pct ?? null)}` : ''}`}
              onPointerEnter={() => setActiu(i)} onPointerLeave={() => setActiu(null)} onFocus={() => setActiu(i)} onBlur={() => setActiu(null)}
              style={{ outline: actiu === i ? undefined : 'none' }}>
              <span className="columna bg-s1" style={{ height: alt(f.pct_proves) }} />
              <span className="columna bg-s2" style={{ height: alt(f.pct_compres) }} />
              {ambProposta && <span className="columna prop" style={{ height: alt(f.proposta_pct) }} />}
            </div>
          ))}
        </div>
        <div className="etiquetes-columnes" style={{ gridTemplateColumns: `repeat(${files.length}, 1fr)` }} aria-hidden="true">
          {files.map((f) => <span key={f.talla}>{f.talla}</span>)}
        </div>
        {actiu !== null && (
          <div className="globus" style={{ top: 0, left: `${Math.min(70, (actiu / files.length) * 100)}%` }}>
            <div className="titol-globus">Talla {files[actiu].talla}</div>
            <div className="fila-globus"><span className="clau-linia bg-s1" /><b>{pct(files[actiu].pct_proves)}</b><span className="nom">de les proves</span></div>
            <div className="fila-globus"><span className="clau-linia bg-s2" /><b>{pct(files[actiu].pct_compres)}</b><span className="nom">de les compres</span></div>
            {ambProposta && <div className="fila-globus"><span className="clau-linia" style={{ background: 'var(--fg-2)' }} /><b>{pct(files[actiu].proposta_pct ?? null)}</b><span className="nom">proposta</span></div>}
          </div>
        )}
      </div>
    </figure>
  );
}
