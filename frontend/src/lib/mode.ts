/**
 * Mode demostració: VITE_MOCK=1 en compilar, o «?mock=1» a l'adreça (es
 * recorda durant la sessió del navegador; «?mock=0» el treu).
 */
const CLAU = 'hebra-mock';

/** Demo d'un sol fitxer (VITE_DEMO=1): dades falses i rutes amb # (funciona en qualsevol adreça). */
export const esDemo = (): boolean => import.meta.env.VITE_DEMO === '1';

/** Adreça d'una pàgina del tauler per a window.location (amb o sense #). */
export const rutaApp = (ruta: string): string => (esDemo() ? `#${ruta}` : `/app${ruta}`);

/** Ruta actual dins del tauler (sense /app ni #). */
export const rutaActual = (): string => (esDemo() ? window.location.hash.replace(/^#/, '') || '/' : window.location.pathname.replace(/^\/app/, '') + window.location.search);

export function esMock(): boolean {
  if (import.meta.env.VITE_MOCK === '1' || esDemo()) return true;
  const q = new URLSearchParams(window.location.search).get('mock');
  try {
    if (q === '1') sessionStorage.setItem(CLAU, '1');
    if (q === '0') sessionStorage.removeItem(CLAU);
    return sessionStorage.getItem(CLAU) === '1';
  } catch {
    return q === '1';
  }
}
