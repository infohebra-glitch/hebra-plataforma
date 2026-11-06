/** Tema del tauler: només Clar (per defecte) i Fosc (docs/ESPECIFICACIO-v3.md, G). */
export type Tema = 'clar' | 'fosc';
export const CLAU_TEMA = 'hebra-tema';

type Magatzem = Pick<Storage, 'getItem' | 'setItem'>;
const local = (): Magatzem | null => { try { return window.localStorage; } catch { return null; } };

/** Qualsevol valor que no sigui «fosc» (també l'antic «sistema») és Clar. */
export function llegeixTema(m: Magatzem | null = local()): Tema {
  try { return m?.getItem(CLAU_TEMA) === 'fosc' ? 'fosc' : 'clar'; } catch { return 'clar'; }
}

export function desaTema(t: Tema, m: Magatzem | null = local()): void {
  try { m?.setItem(CLAU_TEMA, t); } catch { /* sense emmagatzematge: només dura aquesta visita */ }
}

export function aplicaTema(t: Tema, el: { dataset: DOMStringMap } = document.documentElement): void {
  el.dataset.theme = t === 'fosc' ? 'dark' : 'light';
}
