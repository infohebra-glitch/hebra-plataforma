import { useCallback, useEffect, useRef, useState } from 'react';

export interface EstatConsulta<T> {
  dades: T | undefined;
  error: Error | undefined;
  /** Primera càrrega (no hi ha dades encara): mostrem esquelet. */
  carregant: boolean;
  /** Recàrrega amb dades anteriors: les mantenim atenuades, sense salts. */
  recarregant: boolean;
  recarrega: () => void;
}

/** Carrega dades i les torna a carregar quan canvien les dependències. */
export function useApi<T>(carrega: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): EstatConsulta<T> {
  const [dades, setDades] = useState<T>();
  const [error, setError] = useState<Error>();
  const [enCurs, setEnCurs] = useState(true);
  const [versio, setVersio] = useState(0);
  const ref = useRef(carrega);
  ref.current = carrega;

  useEffect(() => {
    const ctrl = new AbortController();
    setEnCurs(true);
    setError(undefined);
    ref.current(ctrl.signal)
      .then((d) => { if (!ctrl.signal.aborted) { setDades(d); setEnCurs(false); } })
      .catch((e: Error) => { if (e.name !== 'AbortError' && !ctrl.signal.aborted) { setError(e); setEnCurs(false); } });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versio]);

  const recarrega = useCallback(() => setVersio((v) => v + 1), []);
  return { dades, error, carregant: enCurs && dades === undefined, recarregant: enCurs && dades !== undefined, recarrega };
}

/** Amplada d'un element (per als gràfics SVG que s'adapten). */
export function useAmplada<E extends HTMLElement>(inicial = 640): [React.RefObject<E>, number] {
  const ref = useRef<E>(null);
  const [w, setW] = useState(inicial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth || inicial);
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [inicial]);
  return [ref, w];
}

/** Preferència desada al navegador (només comoditat: si falla, valor per defecte). */
export function usePreferencia<T extends string>(clau: string, perDefecte: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    try { return (localStorage.getItem(clau) as T | null) ?? perDefecte; } catch { return perDefecte; }
  });
  const desa = useCallback((nou: T) => {
    setV(nou);
    try { localStorage.setItem(clau, nou); } catch { /* sense emmagatzematge */ }
  }, [clau]);
  return [v, desa];
}
