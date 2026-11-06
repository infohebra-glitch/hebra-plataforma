/**
 * Flux en directe GET /api/v2/flux (Server-Sent Events).
 * EventSource ja es reconnecta sol quan la connexió cau; si el navegador la
 * dona per tancada (p. ex. el servidor ha reiniciat), la reobrim amb espera
 * creixent (1 s, 2 s, 4 s... fins a 30 s).
 */
import { construeixUrl } from './client';
import type { EsdevenimentFlux } from './types';

export type EstatFlux = 'connectant' | 'connectat' | 'reconnectant';

export interface OpcionsFlux {
  botiga?: string;
  enEsdeveniment: (e: EsdevenimentFlux) => void;
  enEstat?: (e: EstatFlux) => void;
}

export type ObreFlux = (o: OpcionsFlux) => () => void;

const TIPUS = ['peticio', 'abandonada', 'alerta', 'cabina', 'tasca'] as const;

const fluxReal: ObreFlux = ({ botiga, enEsdeveniment, enEstat }) => {
  let es: EventSource | null = null;
  let espera = 1000;
  let temporitzador: number | undefined;
  let tancat = false;

  const obre = () => {
    enEstat?.(es ? 'reconnectant' : 'connectant');
    es = new EventSource(construeixUrl('/flux', { botiga }), { withCredentials: true });
    es.onopen = () => { espera = 1000; enEstat?.('connectat'); };
    es.onerror = () => {
      if (tancat || !es) return;
      if (es.readyState === EventSource.CLOSED) {
        es.close();
        enEstat?.('reconnectant');
        temporitzador = window.setTimeout(obre, espera);
        espera = Math.min(espera * 2, 30000);
      } else {
        enEstat?.('reconnectant');
      }
    };
    for (const tipus of TIPUS) {
      es.addEventListener(tipus, (ev) => {
        try {
          const dades = JSON.parse((ev as MessageEvent<string>).data);
          enEsdeveniment({ tipus, dades } as EsdevenimentFlux);
        } catch { /* missatge mal format: l'ignorem */ }
      });
    }
  };

  obre();
  return () => { tancat = true; window.clearTimeout(temporitzador); es?.close(); };
};

let obreFluxActual: ObreFlux = fluxReal;
export function configuraFlux(f: ObreFlux): void { obreFluxActual = f; }
export const obreFlux: ObreFlux = (o) => obreFluxActual(o);
