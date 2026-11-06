/**
 * Activa el mode demostració: totes les crides a /api/v2 i el flux SSE es
 * responen dins del navegador, sense backend. Es carrega amb import()
 * dinàmic, de manera que el codi fals no entra al paquet principal.
 */
import { configuraTransport } from '../api/client';
import { configuraFlux } from '../api/flux';
import type { Abandonada } from '../api/types';
import { estat, novaPeticio } from './dades';
import { respon } from './servidor';

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function importaCsv(tipus: string, fitxer: File) {
  const text = await fitxer.text();
  const linies = text.split(/\r?\n/).filter((l) => l.trim());
  if (linies.length < 2) return { importades: 0, errors: ['El fitxer és buit o només té la capçalera.'] };
  const columnes = linies[0].split(/[;,]/).length;
  const errors: string[] = [];
  let importades = 0;
  linies.slice(1).forEach((l, i) => {
    if (l.split(/[;,]/).length !== columnes) errors.push(`Fila ${i + 2}: té un nombre de columnes diferent de la capçalera.`);
    else importades++;
  });
  return { importades, errors, tipus };
}

export function activaMock(): void {
  configuraTransport(async (url, init) => {
    await espera(180 + Math.random() * 220);
    const u = new URL(url, window.location.origin);
    const metode = (init.method ?? 'GET').toUpperCase();
    let cos: unknown;
    if (init.body instanceof FormData) {
      const fitxer = init.body.get('fitxer');
      const imp = u.pathname.match(/importa\/(\w+)$/);
      const r = respon(metode, u, null);
      if (r.estat === 200 && imp && fitxer instanceof File) {
        return new Response(JSON.stringify(await importaCsv(imp[1], fitxer)), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify(r.cos), { status: r.estat, headers: { 'Content-Type': 'application/json' } });
    }
    if (typeof init.body === 'string') cos = JSON.parse(init.body);
    const r = respon(metode, u, cos);
    return new Response(JSON.stringify(r.cos), { status: r.estat, headers: { 'Content-Type': 'application/json' } });
  });

  // Flux fals: una petició nova cada ~25 s i, de tant en tant, una peça abandonada.
  configuraFlux(({ enEsdeveniment, enEstat }) => {
    enEstat?.('connectant');
    const obert = window.setTimeout(() => enEstat?.('connectat'), 400);
    let n = 0;
    const interval = window.setInterval(() => {
      n++;
      if (n % 4 === 0) {
        const a: Abandonada = { id: estat.seguentAbandonada++, epc: `3034F8A1C20000000000${String(n).padStart(4, '0')}`, model: 'SB-25-CRU', nom: 'Sobrecamisa de cotó', talla: 'M', cabina: 'BCN-01-C3', detectada: new Date().toISOString(), resolta: false };
        estat.abandonades.unshift(a);
        enEsdeveniment({ tipus: 'abandonada', dades: a });
      } else {
        enEsdeveniment({ tipus: 'peticio', dades: novaPeticio() });
      }
    }, 25000);
    return () => { window.clearTimeout(obert); window.clearInterval(interval); };
  });
}
