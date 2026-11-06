import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Filtre } from '../api/types';
import { calculaPeriode, type EstatPeriode, type TipusPeriode } from '../lib/periode';
import { useSessio } from './Sessio';

interface ValorFiltre {
  botiga: string;
  setBotiga: (b: string) => void;
  periode: EstatPeriode;
  setPeriode: (tipus: TipusPeriode, des?: string, fins?: string) => void;
  /** El filtre comú que va a totes les crides (botiga, des, fins). */
  filtre: Filtre;
  /** Clau estable per a les dependències dels efectes. */
  clau: string;
}

const Ctx = createContext<ValorFiltre | null>(null);
const CLAU = 'hebra-filtre';

export function useFiltre(): ValorFiltre {
  const v = useContext(Ctx);
  if (!v) throw new Error('useFiltre fora de <ProveidorFiltre>');
  return v;
}

function llegeix(): { botiga?: string; periode?: EstatPeriode } {
  try { return JSON.parse(sessionStorage.getItem(CLAU) ?? '{}'); } catch { return {}; }
}

export function ProveidorFiltre({ children }: { children: ReactNode }) {
  const { usuari, botigues } = useSessio();
  const desat = llegeix();
  const fixa = usuari.rol === 'botiga' ? usuari.botiga_id ?? botigues[0]?.id ?? '' : null;
  const [botiga, setBotigaEstat] = useState<string>(fixa ?? (desat.botiga && botigues.some((b) => b.id === desat.botiga) ? desat.botiga : ''));
  const [periode, setPeriodeEstat] = useState<EstatPeriode>(() => {
    const p = desat.periode;
    if (p?.tipus === 'personalitzat' && p.des && p.fins) return p;
    const tipus = p?.tipus && p.tipus !== 'personalitzat' ? p.tipus : 'aquesta';
    return { tipus, ...calculaPeriode(tipus) };
  });

  const valor = useMemo<ValorFiltre>(() => {
    const desa = (b: string, p: EstatPeriode) => { try { sessionStorage.setItem(CLAU, JSON.stringify({ botiga: b, periode: p })); } catch { /* res */ } };
    const filtre: Filtre = { botiga: botiga || undefined, des: periode.des, fins: periode.fins };
    return {
      botiga,
      setBotiga: (b) => { if (fixa === null) { setBotigaEstat(b); desa(b, periode); } },
      periode,
      setPeriode: (tipus, des, fins) => {
        const p: EstatPeriode = tipus === 'personalitzat' ? { tipus, des: des ?? periode.des, fins: fins ?? periode.fins } : { tipus, ...calculaPeriode(tipus) };
        setPeriodeEstat(p); desa(botiga, p);
      },
      filtre,
      clau: `${filtre.botiga ?? '*'}|${filtre.des}|${filtre.fins}`,
    };
  }, [botiga, periode, fixa]);

  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}
