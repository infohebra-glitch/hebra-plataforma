import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';
import { sessio } from '../api/endpoints';
import type { Botiga, Rol, Usuari } from '../api/types';
import { rutaApp } from '../lib/mode';
import { useApi } from '../lib/useApi';
import { ErrorEstat, Esquelet } from '../components/Estat';

interface ValorSessio {
  usuari: Usuari;
  botigues: Botiga[];
  surt: () => Promise<void>;
  pot: (...rols: Rol[]) => boolean;
}

const Ctx = createContext<ValorSessio | null>(null);

export function useSessio(): ValorSessio {
  const v = useContext(Ctx);
  if (!v) throw new Error('useSessio fora de <ProveidorSessio>');
  return v;
}

/** Carrega GET /jo; si no hi ha sessió, el client ja redirigeix a /app/entra. */
export function ProveidorSessio({ children }: { children: ReactNode }) {
  const q = useApi(() => sessio.jo(), []);
  const surt = useCallback(async () => {
    try { await sessio.surt(); } finally { window.location.assign(rutaApp('/entra')); }
  }, []);
  const valor = useMemo<ValorSessio | null>(() => (q.dades ? {
    usuari: q.dades.usuari,
    botigues: q.dades.botigues,
    surt,
    pot: (...rols) => rols.includes(q.dades!.usuari.rol),
  } : null), [q.dades, surt]);

  if (q.error) return <main className="contingut"><ErrorEstat error={q.error} reintenta={q.recarrega} /></main>;
  if (!valor) return <main className="contingut" aria-busy="true"><span className="sr-only">Carregant la sessió…</span><Esquelet tipus="rajoles" /></main>;
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}
