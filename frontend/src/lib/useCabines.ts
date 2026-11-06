/**
 * Estat de les cabines en directe: GET /provadors/directe i, a sobre, els
 * esdeveniments «cabina» del flux SSE. Es recarrega sencer cada minut per si
 * s'ha perdut algun esdeveniment.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { provadors } from '../api/endpoints';
import { obreFlux, type EstatFlux } from '../api/flux';
import type { CabinaDirecte, ProvadorsDirecte } from '../api/types';

export function resumDe(cabines: CabinaDirecte[]): ProvadorsDirecte['resum'] {
  return {
    ocupades: cabines.filter((c) => c.estat === 'ocupada').length,
    lliures: cabines.filter((c) => c.estat === 'lliure').length,
    sessions_avui: cabines.reduce((s, c) => s + c.avui.sessions, 0),
    proves_avui: cabines.reduce((s, c) => s + c.avui.proves, 0),
  };
}

/** Substitueix (o afegeix) una cabina i recalcula el resum. Pura. */
export function aplicaCabina(d: ProvadorsDirecte, c: CabinaDirecte): ProvadorsDirecte {
  const cabines = d.cabines.some((x) => x.cabina_id === c.cabina_id) ? d.cabines.map((x) => (x.cabina_id === c.cabina_id ? c : x)) : [...d.cabines, c];
  return { ...d, cabines, resum: resumDe(cabines), generat: new Date().toISOString() };
}

export function useCabines(botiga: string | undefined, { flux = true }: { flux?: boolean } = {}) {
  const [dades, setDades] = useState<ProvadorsDirecte>();
  const [error, setError] = useState<Error>();
  const [estatFlux, setEstatFlux] = useState<EstatFlux>('connectant');
  const [darrerCanvi, setDarrerCanvi] = useState<{ id: string; text: string } | null>(null);
  const filtra = useRef(botiga);
  filtra.current = botiga;

  const carrega = useCallback(async () => {
    try { setDades(await provadors.directe(botiga)); setError(undefined); } catch (e) { setError(e as Error); }
  }, [botiga]);
  useEffect(() => { setDades(undefined); void carrega(); const i = window.setInterval(carrega, 60000); return () => window.clearInterval(i); }, [carrega]);

  const aplica = useCallback((c: CabinaDirecte) => {
    if (filtra.current && c.botiga_id !== filtra.current) return;
    setDades((d) => (d ? aplicaCabina(d, c) : d));
    setDarrerCanvi({ id: c.cabina_id, text: `${c.nom}: ${NOM_ESTAT[c.estat].toLowerCase()}` });
  }, []);

  useEffect(() => {
    if (!flux) return undefined;
    return obreFlux({ botiga, enEstat: setEstatFlux, enEsdeveniment: (e) => { if (e.tipus === 'cabina') aplica(e.dades); } });
  }, [botiga, flux, aplica]);

  return { dades, error, recarrega: carrega, aplica, estatFlux, darrerCanvi };
}

export const NOM_ESTAT: Record<CabinaDirecte['estat'], string> = {
  ocupada: 'Ocupada', lliure: 'Lliure', porta_oberta: 'Porta oberta', sense_dades: 'Sense dades',
};

/** «fa 40 s», «fa 4 min», «fa 2 h 5 min». */
export function faTemps(iso: string | null | undefined, ara = Date.now()): string {
  if (!iso) return '—';
  const s = Math.max(0, Math.round((ara - Date.parse(iso)) / 1000));
  if (s < 60) return `fa ${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `fa ${m} min`;
  const h = Math.floor(m / 60);
  return `fa ${h} h${m % 60 ? ` ${m % 60} min` : ''}`;
}
