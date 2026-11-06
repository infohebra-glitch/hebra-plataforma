/**
 * Mode demostració: VITE_MOCK=1 en compilar, o «?mock=1» a l'adreça (es
 * recorda durant la sessió del navegador; «?mock=0» el treu).
 */
const CLAU = 'hebra-mock';

export function esMock(): boolean {
  if (import.meta.env.VITE_MOCK === '1') return true;
  const q = new URLSearchParams(window.location.search).get('mock');
  try {
    if (q === '1') sessionStorage.setItem(CLAU, '1');
    if (q === '0') sessionStorage.removeItem(CLAU);
    return sessionStorage.getItem(CLAU) === '1';
  } catch {
    return q === '1';
  }
}
