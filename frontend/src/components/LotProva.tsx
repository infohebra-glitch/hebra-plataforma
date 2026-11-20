/**
 * Lot de prova: dades inventades en una botiga pròpia («Botiga de prova») perquè la marca vegi
 * com quedarà el tauler. Es carrega i s'esborra d'un clic; les dades reals no es toquen mai.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { lotProva } from '../api/endpoints';
import type { EstatLotProva } from '../api/types';
import { useSessio } from '../context/Sessio';
import { diaCurt as dataCurta } from '../lib/format';
import { Icona } from './Icones';

interface ValorLot { lot: EstatLotProva | null; carrega: () => Promise<void>; esborra: () => Promise<void>; ocupat: 'carrega' | 'esborra' | null; error: string | null }
const Ctx = createContext<ValorLot>({ lot: null, carrega: async () => {}, esborra: async () => {}, ocupat: null, error: null });

export function ProveidorLotProva({ children }: { children: ReactNode }) {
  const { usuari } = useSessio();
  const potGestionar = usuari.rol !== 'botiga';
  const [lot, setLot] = useState<EstatLotProva | null>(null);
  const [ocupat, setOcupat] = useState<ValorLot['ocupat']>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!potGestionar) return;
    const c = new AbortController();
    lotProva.estat(c.signal).then(setLot).catch(() => {});
    return () => c.abort();
  }, [potGestionar]);
  // Després de carregar o esborrar, recarreguem: canvia la llista de botigues i totes les xifres.
  const fes = useCallback(async (que: 'carrega' | 'esborra') => {
    setOcupat(que); setError(null);
    try {
      if (que === 'carrega') await lotProva.carrega(); else await lotProva.esborra();
      window.location.reload();
    } catch (e) { setError((e as Error).message); setOcupat(null); }
  }, []);
  return <Ctx.Provider value={{ lot, carrega: () => fes('carrega'), esborra: () => fes('esborra'), ocupat, error }}>{children}</Ctx.Provider>;
}

export const useLotProva = () => useContext(Ctx);

/** Botó d'esborrar en dos passos (sense diàlegs del navegador). */
function BotoEsborra({ classe }: { classe?: string }) {
  const { esborra, ocupat } = useLotProva();
  const [segur, setSegur] = useState(false);
  useEffect(() => { if (!segur) return; const t = setTimeout(() => setSegur(false), 6000); return () => clearTimeout(t); }, [segur]);
  if (ocupat === 'esborra') return <button type="button" className={classe} disabled>Esborrant…</button>;
  return segur
    ? <button type="button" className={classe} onClick={esborra} autoFocus>Sí, esborra-ho tot</button>
    : <button type="button" className={classe} onClick={() => setSegur(true)}><Icona nom="paperera" mida={15} />Esborra el lot de prova</button>;
}

/** Franja a dalt de tot mentre hi ha un lot de prova carregat. */
export function FranjaLotProva() {
  const { lot, error } = useLotProva();
  if (!lot?.carregat) return null;
  return (
    <div className="franja-prova" role="status">
      <span><b>Hi ha dades de prova</b> a «{lot.nom}». Són inventades i no es barregen amb les reals. {error && <b>{error}</b>}</span>
      <BotoEsborra />
    </div>
  );
}

/** Targeta per carregar o esborrar el lot (Connexions i dades, i el resum quan no hi ha dades). */
export function TargetaLotProva({ compacta }: { compacta?: boolean }) {
  const { lot, carrega, ocupat, error } = useLotProva();
  if (!lot) return null;
  return (
    <section className="targeta targeta-lot" aria-labelledby="t-lot">
      <div className="targeta-cap">
        <h2 id="t-lot" style={{ fontSize: 19 }}><Icona nom="prova" mida={18} /> Lot de prova</h2>
        {lot.carregat && <span className="insignia insignia-marca">Carregat</span>}
      </div>
      {lot.carregat ? (
        <>
          <p className="muted" style={{ margin: 0 }}>
            «{lot.nom}» té dades inventades{lot.des && lot.fins ? <> (del {dataCurta(lot.des)} al {dataCurta(lot.fins)})</> : null}.
            Tria-la al selector de botiga per veure-la sola. Quan l’esborris, desapareix tot el que és de prova i res més.
          </p>
          {lot.resum && (
            <ul className="estat-lot">
              <li><b>{lot.resum.sessions.toLocaleString('ca')}</b><span>sessions de cabina</span></li>
              <li><b>{lot.resum.proves.toLocaleString('ca')}</b><span>peces provades</span></li>
              <li><b>{lot.resum.vendes.toLocaleString('ca')}</b><span>línies de venda</span></li>
              <li><b>{lot.resum.peces}</b><span>models</span></li>
            </ul>
          )}
          <div className="fila"><BotoEsborra /></div>
        </>
      ) : (
        <>
          <p className="muted" style={{ margin: 0 }}>
            {compacta ? 'Omple el tauler amb dues setmanes d’un pilot inventat per veure com quedarà.' :
              'Crea una «Botiga de prova» amb 3 cabines i dues setmanes d’un pilot inventat (proves, vendes, fitxa NFC, peticions de talla, estoc i informes), per veure com quedarà la plataforma. Va a part: no toca cap dada real, no envia cap correu i s’esborra d’un sol clic.'}
          </p>
          <div className="fila">
            <button type="button" className="boto-primari" onClick={carrega} disabled={!!ocupat}>
              {ocupat === 'carrega' ? 'Creant les dades… (uns segons)' : <><Icona nom="prova" mida={16} />Carrega el lot de prova</>}
            </button>
          </div>
        </>
      )}
      {error && <p className="missatge-error" role="alert" style={{ margin: 0 }}>{error}</p>}
    </section>
  );
}
