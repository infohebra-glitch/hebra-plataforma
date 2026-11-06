/**
 * Web del dependent (mòbil, una mà): peticions de talla en directe pel flux SSE,
 * amb botons grans, avisos de talla esgotada i peces abandonades per recollir.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { analitica, operacio } from '../api/endpoints';
import { obreFlux, type EstatFlux } from '../api/flux';
import type { Abandonada, Alerta, EstatPeticio, Peticio } from '../api/types';
import { ErrorEstat, Esquelet } from '../components/Estat';
import { LogoHebra } from '../components/Icones';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { hora, isoData } from '../lib/format';
import { usePreferencia } from '../lib/useApi';

const OBERTES: EstatPeticio[] = ['pendent', 'en_cami'];

/** Dues notes suaus amb WebAudio (sense fitxers) i una vibració curta. */
function useAvis(actiu: boolean) {
  const ctx = useRef<AudioContext | null>(null);
  const prepara = useCallback(() => {
    if (!ctx.current && typeof AudioContext !== 'undefined') ctx.current = new AudioContext();
    void ctx.current?.resume();
  }, []);
  const avisa = useCallback(() => {
    if (!actiu) return;
    try { navigator.vibrate?.([120, 60, 120]); } catch { /* sense vibració */ }
    const c = ctx.current;
    if (!c) return;
    [660, 880].forEach((f, i) => {
      const o = c.createOscillator(), g = c.createGain();
      o.type = 'sine'; o.frequency.value = f;
      const t = c.currentTime + i * 0.18;
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.12, t + 0.02); g.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
      o.connect(g).connect(c.destination); o.start(t); o.stop(t + 0.4);
    });
  }, [actiu]);
  return { prepara, avisa };
}

function useAra(intervalMs = 1000) {
  const [ara, setAra] = useState(Date.now());
  useEffect(() => { const i = window.setInterval(() => setAra(Date.now()), intervalMs); return () => window.clearInterval(i); }, [intervalMs]);
  return ara;
}

function Espera({ des }: { des: string }) {
  const ara = useAra();
  const s = Math.max(0, Math.round((ara - Date.parse(des)) / 1000));
  const txt = s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`;
  return <span className={`espera${s > 90 ? ' llarga' : ''}`}>fa {txt}</span>;
}

function TargetaPeticio({ p, nova, enCanvi }: { p: Peticio; nova: boolean; enCanvi: (p: Peticio, e: Exclude<EstatPeticio, 'pendent'>) => void }) {
  const cabina = p.cabina.match(/C(\d+)$/)?.[1] ?? p.cabina;
  return (
    <li className={`peticio${nova ? ' nova' : ''}`} aria-label={`Cabina ${cabina}: ${p.nom}, talla ${p.talla}`}>
      <div className="peticio-cap">
        <div>
          <div className="que">{p.nom}</div>
          <div className="on">{p.color} · <b>Cabina {cabina}</b></div>
          <div className="petit muted">Demanada a les {hora(p.hora_peticio)} · <Espera des={p.hora_peticio} /></div>
          {!p.disponible && <span className="insignia insignia-critic" style={{ marginTop: 6 }}>Sense estoc al sistema</span>}
          {p.estat === 'en_cami' && <span className="insignia insignia-neutra" style={{ marginTop: 6 }}>En camí</span>}
        </div>
        <div className="talla-gran" aria-label={`Talla ${p.talla}`}>{p.talla}</div>
      </div>
      <div className="botons-grans">
        <button type="button" className="boto-gran" aria-pressed={p.estat === 'en_cami'} onClick={() => enCanvi(p, 'en_cami')}>En camí</button>
        <button type="button" className="boto-gran lliurada" onClick={() => enCanvi(p, 'lliurada')}>Lliurada</button>
        <button type="button" className="boto-gran no-hi-ha" onClick={() => enCanvi(p, 'no_disponible')}>No n’hi ha</button>
      </div>
    </li>
  );
}

export function Dependent() {
  const { usuari, botigues } = useSessio();
  const { botiga, setBotiga } = useFiltre();
  const [peticions, setPeticions] = useState<Peticio[] | null>(null);
  const [abandonades, setAbandonades] = useState<Abandonada[] | null>(null);
  const [esgotades, setEsgotades] = useState<Alerta[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [avisError, setAvisError] = useState<string | null>(null);
  const [estatFlux, setEstatFlux] = useState<EstatFlux>('connectant');
  const [noves, setNoves] = useState<Set<number>>(new Set());
  const [so, setSo] = usePreferencia<'si' | 'no'>('hebra-so', 'si');
  const { prepara, avisa } = useAvis(so === 'si');
  const avisaRef = useRef(avisa);
  avisaRef.current = avisa;
  const llistaRef = useRef(peticions);
  llistaRef.current = peticions;
  const b = botiga || undefined;

  useEffect(() => { document.title = 'Peticions · Hebra'; }, []);

  const carrega = useCallback(async () => {
    try {
      const avui = isoData(new Date());
      const [p, a, al] = await Promise.all([operacio.peticions(b), operacio.abandonades(b),
        analitica.alertes({ botiga: b, des: avui, fins: avui })]);
      setPeticions(p.peticions.filter((x) => OBERTES.includes(x.estat)));
      setAbandonades(a.abandonades.filter((x) => !x.resolta));
      setEsgotades(al.alertes.filter((x) => x.tipus === 'talla_esgotada'));
      setError(null);
    } catch (e) { setError(e as Error); }
  }, [b]);

  useEffect(() => { void carrega(); const i = window.setInterval(carrega, 60000); return () => window.clearInterval(i); }, [carrega]);

  useEffect(() => obreFlux({
    botiga: b,
    enEstat: (e) => { setEstatFlux(e); if (e === 'connectat') void carrega(); },
    enEsdeveniment: (ev) => {
      if (ev.tipus === 'peticio') {
        const p = ev.dades;
        const esNova = !(llistaRef.current ?? []).some((x) => x.id === p.id);
        if (esNova && p.estat === 'pendent') {
          avisaRef.current();
          setNoves((s) => new Set(s).add(p.id));
          window.setTimeout(() => setNoves((s) => { const n = new Set(s); n.delete(p.id); return n; }), 4000);
        }
        setPeticions((llista) => {
          const resta = (llista ?? []).filter((x) => x.id !== p.id);
          return OBERTES.includes(p.estat) ? [p, ...resta] : resta;
        });
      } else if (ev.tipus === 'abandonada') {
        const a = ev.dades;
        setAbandonades((llista) => { const resta = (llista ?? []).filter((x) => x.id !== a.id); return a.resolta ? resta : [a, ...resta]; });
      } else if (ev.tipus === 'alerta' && ev.dades.tipus === 'talla_esgotada') {
        const al = ev.dades;
        avisaRef.current();
        setEsgotades((llista) => [al, ...llista.filter((x) => x.id !== al.id)]);
      }
    },
  }), [b, carrega]);

  const canvia = async (p: Peticio, estat: Exclude<EstatPeticio, 'pendent'>) => {
    prepara();
    const abans = peticions;
    setAvisError(null);
    setPeticions((l) => (l ?? []).flatMap((x) => (x.id !== p.id ? [x] : estat === 'en_cami' ? [{ ...x, estat }] : [])));
    try { await operacio.canviaPeticio(p.id, estat); }
    catch (e) { setPeticions(abans); setAvisError(`No s’ha pogut desar: ${(e as Error).message}`); }
  };
  const recull = async (a: Abandonada) => {
    const abans = abandonades;
    setAbandonades((l) => (l ?? []).filter((x) => x.id !== a.id));
    try { await operacio.recull(a.id); }
    catch (e) { setAbandonades(abans); setAvisError(`No s’ha pogut desar: ${(e as Error).message}`); }
  };

  const ordenades = [...(peticions ?? [])].sort((x, y) => (x.estat === y.estat ? Date.parse(x.hora_peticio) - Date.parse(y.hora_peticio) : x.estat === 'pendent' ? -1 : 1));
  const nomEstat = { connectant: 'Connectant…', connectat: 'En directe', reconnectant: 'Reconnectant…' }[estatFlux];

  return (
    <div className="dependent" onPointerDown={prepara}>
      <a href="#peticions" className="salta">Salta a les peticions</a>
      <header className="dependent-cap">
        <span className="marca-hebra"><LogoHebra />Peticions</span>
        <span className={`estat-connexio ${estatFlux}`} role="status">{nomEstat}</span>
      </header>
      <div className="fila entre" style={{ marginBottom: 8 }}>
        <label className="interruptor"><input type="checkbox" checked={so === 'si'} onChange={(e) => { setSo(e.target.checked ? 'si' : 'no'); prepara(); }} />So i vibració</label>
        {usuari.rol !== 'botiga' && (
          <>
            <label className="sr-only" htmlFor="dep-botiga">Botiga</label>
            <select id="dep-botiga" value={botiga} onChange={(e) => setBotiga(e.target.value)}>
              <option value="">Totes</option>{botigues.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}
            </select>
          </>
        )}
      </div>
      {avisError && <p className="missatge-error" role="alert">{avisError}</p>}
      {error && !peticions && <ErrorEstat error={error} reintenta={carrega} />}

      {esgotades.length > 0 && (
        <section aria-labelledby="t-esgotades" className="panell" style={{ marginBottom: 16, borderColor: 'var(--critical)' }}>
          <h2 id="t-esgotades" style={{ fontSize: 17, margin: '0 0 6px' }}>Talles esgotades que demanen</h2>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {esgotades.map((x) => <li key={x.id}>{x.text}</li>)}
          </ul>
          <p className="petit muted" style={{ margin: '6px 0 0' }}>Digues-ho a l’encarregada i mira si n’hi ha en una altra botiga.</p>
        </section>
      )}

      <section id="peticions" aria-labelledby="t-peticions">
        <h1 id="t-peticions" style={{ fontSize: 22, margin: '8px 0 10px' }}>Talles demanades {peticions ? <span className="muted">({ordenades.length})</span> : null}</h1>
        {!peticions && !error && <Esquelet tipus="taula" files={3} />}
        {peticions && !ordenades.length && <div className="panell buit"><h3>Cap petició pendent</h3><p>Quan un client demani una talla des de la cabina, apareixerà aquí{so === 'si' ? ' i sonarà un avís' : ''}.</p></div>}
        <ul className="llista-targetes" aria-live="polite">
          {ordenades.map((p) => <TargetaPeticio key={p.id} p={p} nova={noves.has(p.id)} enCanvi={canvia} />)}
        </ul>
      </section>

      <section aria-labelledby="t-abandonades" style={{ marginTop: 24 }}>
        <h2 id="t-abandonades" style={{ fontSize: 19, marginBottom: 4 }}>Peces per recollir {abandonades?.length ? <span className="muted">({abandonades.length})</span> : null}</h2>
        <p className="petit muted">Han sortit de la sala fa més de 30 minuts i no s’han venut.</p>
        {abandonades && !abandonades.length && <p className="muted">Cap peça per recollir.</p>}
        <ul className="llista-targetes">
          {(abandonades ?? []).map((a) => (
            <li key={a.id} className="targeta">
              <div className="targeta-cap">
                <div><b>{a.nom}</b> · talla {a.talla}<div className="petit muted">Cabina {a.cabina.match(/C(\d+)$/)?.[1] ?? a.cabina} · des de les {hora(a.detectada)}</div></div>
                <button type="button" className="boto-gran" style={{ minWidth: 120 }} onClick={() => recull(a)}>Recollida</button>
              </div>
            </li>
          ))}
        </ul>
      </section>
      {usuari.rol !== 'botiga' && <p className="petit" style={{ marginTop: 24 }}><Link to="/">← Torna al tauler</Link></p>}
    </div>
  );
}
