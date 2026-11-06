/** Estats comuns: càrrega (esquelet), buit i error, amb text útil en català. */
import type { ReactNode } from 'react';
import { ErrorApi } from '../api/client';
import type { EstatConsulta } from '../lib/useApi';

export function Esquelet({ tipus = 'bloc', files = 5 }: { tipus?: 'rajoles' | 'grafic' | 'taula' | 'bloc'; files?: number }) {
  if (tipus === 'rajoles') {
    return <div className="rajoles" aria-hidden="true">{Array.from({ length: 6 }, (_, i) => <div key={i} className="rajola"><div className="esquelet" style={{ height: 14, width: '60%' }} /><div className="esquelet" style={{ height: 28, width: '45%', marginTop: 6 }} /><div className="esquelet" style={{ height: 11, width: '70%', marginTop: 6 }} /></div>)}</div>;
  }
  if (tipus === 'grafic') return <div className="esquelet" style={{ height: 240 }} aria-hidden="true" />;
  if (tipus === 'taula') return <div aria-hidden="true" style={{ display: 'grid', gap: 8 }}>{Array.from({ length: files }, (_, i) => <div key={i} className="esquelet" style={{ height: 30 }} />)}</div>;
  return <div className="esquelet" style={{ height: 120 }} aria-hidden="true" />;
}

export function Buit({ titol, children, accio }: { titol: string; children?: ReactNode; accio?: ReactNode }) {
  return (
    <div className="buit" role="status">
      <h3>{titol}</h3>
      {children && <p>{children}</p>}
      {accio}
    </div>
  );
}

export function ErrorEstat({ error, reintenta }: { error: Error; reintenta?: () => void }) {
  const missatge = error instanceof ErrorApi ? error.message : 'Alguna cosa no ha anat bé en carregar aquestes dades.';
  return (
    <div className="error-estat" role="alert">
      <div><b>No s’han pogut carregar les dades.</b> <span>{missatge}</span></div>
      {reintenta && <button type="button" onClick={reintenta}>Torna-ho a provar</button>}
    </div>
  );
}

/**
 * Pinta una consulta: esquelet la primera vegada, error si falla i, quan hi ha
 * dades, el contingut (atenuat mentre es recarrega, sense salts de disseny).
 */
export function Consulta<T>({ q, esquelet = <Esquelet />, children }: { q: EstatConsulta<T>; esquelet?: ReactNode; children: (d: T) => ReactNode }) {
  if (q.error && !q.dades) return <ErrorEstat error={q.error} reintenta={q.recarrega} />;
  if (q.carregant || q.dades === undefined) return <div aria-busy="true"><span className="sr-only">Carregant…</span>{esquelet}</div>;
  return (
    <div className={q.recarregant ? 'recarregant' : undefined} aria-busy={q.recarregant}>
      {q.error && <ErrorEstat error={q.error} reintenta={q.recarrega} />}
      {children(q.dades)}
    </div>
  );
}
