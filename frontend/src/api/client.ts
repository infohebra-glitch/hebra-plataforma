/**
 * Client HTTP de /api/v2. Un sol punt d'entrada per a totes les crides:
 * - galetes de sessió (credentials 'same-origin'),
 * - errors amb el `detail` en català del servidor,
 * - 401 → cap a /app/entra (tret que ja hi siguem).
 *
 * En mode demostració (vegeu src/mock), `transport` es reemplaça per un
 * servidor fals en memòria i la resta del codi no se n'assabenta.
 */
import type { Filtre } from './types';

export const BASE = '/api/v2';

export class ErrorApi extends Error {
  constructor(public estat: number, missatge: string) {
    super(missatge);
    this.name = 'ErrorApi';
  }
}

export type Transport = (url: string, init: RequestInit) => Promise<Response>;

let transport: Transport = (url, init) => fetch(url, init);
let enNoAutenticat: () => void = () => {
  if (!window.location.pathname.startsWith('/app/entra')) {
    const tornar = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.assign(`/app/entra?torna=${tornar}`);
  }
};

/** Per al mode demostració i per a les proves. */
export function configuraTransport(t: Transport): void { transport = t; }
export function configuraNoAutenticat(f: () => void): void { enNoAutenticat = f; }

type Params = Record<string, string | number | boolean | null | undefined>;

export function construeixUrl(ruta: string, params?: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
  }
  const s = q.toString();
  return `${BASE}${ruta}${s ? `?${s}` : ''}`;
}

/** El filtre comú en paràmetres de consulta (botiga, des, fins). */
export function paramsFiltre(f?: Filtre): Params {
  return { botiga: f?.botiga, des: f?.des, fins: f?.fins };
}

async function llegeixError(r: Response): Promise<string> {
  try {
    const cos = (await r.json()) as { detail?: unknown };
    if (typeof cos.detail === 'string') return cos.detail;
    if (Array.isArray(cos.detail)) return 'Hi ha dades que no són vàlides.';
  } catch { /* cos buit o no JSON */ }
  if (r.status === 403) return 'No tens permís per veure això.';
  if (r.status === 404) return 'No s’ha trobat.';
  if (r.status >= 500) return 'El servidor ha fallat. Torna-ho a provar d’aquí a una estona.';
  return `Error ${r.status}`;
}

export async function peticio<T>(metode: string, ruta: string, opcions: { params?: Params; cos?: unknown; formulari?: FormData; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  let body: BodyInit | undefined;
  if (opcions.formulari) body = opcions.formulari;
  else if (opcions.cos !== undefined) { body = JSON.stringify(opcions.cos); headers['Content-Type'] = 'application/json'; }

  let r: Response;
  try {
    r = await transport(construeixUrl(ruta, opcions.params), { method: metode, headers, body, credentials: 'same-origin', signal: opcions.signal });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ErrorApi(0, 'No hi ha connexió amb el servidor. Comprova la xarxa.');
  }
  if (r.status === 401 && ruta !== '/sessio') {
    enNoAutenticat();
    throw new ErrorApi(401, 'Cal tornar a entrar.');
  }
  if (!r.ok) throw new ErrorApi(r.status, await llegeixError(r));
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export const api = {
  get: <T>(ruta: string, params?: Params, signal?: AbortSignal) => peticio<T>('GET', ruta, { params, signal }),
  post: <T>(ruta: string, cos?: unknown, params?: Params) => peticio<T>('POST', ruta, { cos, params }),
  patch: <T>(ruta: string, cos: unknown) => peticio<T>('PATCH', ruta, { cos }),
  put: <T>(ruta: string, cos: unknown) => peticio<T>('PUT', ruta, { cos }),
  del: <T>(ruta: string) => peticio<T>('DELETE', ruta),
  puja: <T>(ruta: string, fitxer: File) => {
    const f = new FormData();
    f.append('fitxer', fitxer);
    return peticio<T>('POST', ruta, { formulari: f });
  },
};
