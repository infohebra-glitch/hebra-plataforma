/**
 * Estructura del tauler: barra lateral a l'escriptori, navegació inferior i
 * calaix al mòbil, capçalera amb botiga, període i menú d'usuari.
 */
import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import type { Rol } from '../api/types';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { NOMS_PERIODE, type TipusPeriode } from '../lib/periode';
import { esMock } from '../lib/mode';
import { usePreferencia } from '../lib/useApi';
import { Icona, LogoHebra } from './Icones';

interface Enllac { a: string; nom: string; icona: string; rols?: Rol[]; grup: string }
const MARCA: Rol[] = ['admin', 'marca'];

export const ENLLACOS: Enllac[] = [
  { a: '/', nom: 'Resum', icona: 'resum', grup: 'Tauler' },
  { a: '/peces', nom: 'Peces', icona: 'peces', grup: 'Tauler' },
  { a: '/talles', nom: 'Talles', icona: 'talles', grup: 'Tauler' },
  { a: '/per-que', nom: 'Per què no compren', icona: 'perque', grup: 'Tauler' },
  { a: '/origen', nom: 'Origen i proves', icona: 'origen', grup: 'Tauler', rols: MARCA },
  { a: '/servei', nom: 'Servei', icona: 'servei', grup: 'Botiga' },
  { a: '/estoc', nom: 'Estoc', icona: 'estoc', grup: 'Botiga' },
  { a: '/dependent', nom: 'Web del dependent', icona: 'dependent', grup: 'Botiga' },
  { a: '/decisions', nom: 'Decisions', icona: 'decisions', grup: 'Gestió', rols: MARCA },
  { a: '/valor', nom: 'Valor estimat', icona: 'valor', grup: 'Gestió', rols: MARCA },
  { a: '/informes', nom: 'Informes', icona: 'informes', grup: 'Gestió' },
  { a: '/dades', nom: 'Importa dades', icona: 'dades', grup: 'Gestió' },
];

function useEnllacos() {
  const { usuari } = useSessio();
  return ENLLACOS.filter((e) => !e.rols || e.rols.includes(usuari.rol));
}

function Navegacio({ enTria }: { enTria?: () => void }) {
  const enllacos = useEnllacos();
  const grups = [...new Set(enllacos.map((e) => e.grup))];
  return (
    <nav aria-label="Seccions del tauler">
      {grups.map((g) => (
        <div key={g}>
          <div className="nav-grup">{g}</div>
          <ul className="nav-llista">
            {enllacos.filter((e) => e.grup === g).map((e) => (
              <li key={e.a}><NavLink to={e.a} end={e.a === '/'} onClick={enTria}><Icona nom={e.icona} />{e.nom}</NavLink></li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SelectorFiltres() {
  const { botigues, usuari } = useSessio();
  const { botiga, setBotiga, periode, setPeriode } = useFiltre();
  return (
    <div className="filtres" role="group" aria-label="Filtres">
      <label className="sr-only" htmlFor="sel-botiga">Botiga</label>
      <select id="sel-botiga" value={botiga} onChange={(e) => setBotiga(e.target.value)} disabled={usuari.rol === 'botiga'}>
        {usuari.rol !== 'botiga' && <option value="">Totes les botigues</option>}
        {botigues.map((b) => <option key={b.id} value={b.id}>{b.nom}</option>)}
      </select>
      <label className="sr-only" htmlFor="sel-periode">Període</label>
      <select id="sel-periode" value={periode.tipus} onChange={(e) => setPeriode(e.target.value as TipusPeriode)}>
        {(Object.keys(NOMS_PERIODE) as TipusPeriode[]).map((t) => <option key={t} value={t}>{NOMS_PERIODE[t]}</option>)}
      </select>
      {periode.tipus === 'personalitzat' && (
        <span className="periode-personalitzat">
          <label className="sr-only" htmlFor="data-des">Des de</label>
          <input id="data-des" type="date" value={periode.des} max={periode.fins} onChange={(e) => e.target.value && setPeriode('personalitzat', e.target.value, periode.fins)} />
          <span aria-hidden="true">–</span>
          <label className="sr-only" htmlFor="data-fins">Fins a</label>
          <input id="data-fins" type="date" value={periode.fins} min={periode.des} onChange={(e) => e.target.value && setPeriode('personalitzat', periode.des, e.target.value)} />
        </span>
      )}
    </div>
  );
}

const ROLS: Record<Rol, string> = { admin: 'Administració', marca: 'Marca', botiga: 'Botiga' };

export function aplicaTema(t: string) {
  const r = document.documentElement;
  if (t === 'clar') r.dataset.theme = 'light';
  else if (t === 'fosc') r.dataset.theme = 'dark';
  else delete r.dataset.theme;
}

function MenuUsuari() {
  const { usuari, surt } = useSessio();
  const [obert, setObert] = useState(false);
  const [tema, setTema] = usePreferencia<'sistema' | 'clar' | 'fosc'>('hebra-tema', 'sistema');
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { aplicaTema(tema); }, [tema]);
  useEffect(() => {
    if (!obert) return;
    const fora = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setObert(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setObert(false); };
    document.addEventListener('mousedown', fora);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', fora); document.removeEventListener('keydown', esc); };
  }, [obert]);
  const inicials = usuari.nom.split(' ').map((p) => p[0]).slice(0, 2).join('');
  return (
    <div className="menu-usuari" ref={ref}>
      <button type="button" className="boto-fantasma" aria-expanded={obert} aria-haspopup="true" onClick={() => setObert(!obert)} style={{ padding: 4 }}>
        <span className="avatar" aria-hidden="true">{inicials}</span><span className="sr-only">Menú de {usuari.nom}</span>
      </button>
      {obert && (
        <div className="menu-usuari-panell">
          <div><b>{usuari.nom}</b><div className="petit muted">{usuari.correu} · {ROLS[usuari.rol]}</div></div>
          <label className="camp"><span>Aparença</span>
            <select value={tema} onChange={(e) => setTema(e.target.value as 'sistema' | 'clar' | 'fosc')}>
              <option value="sistema">La del sistema</option><option value="clar">Clara</option><option value="fosc">Fosca</option>
            </select>
          </label>
          {esMock() && <p className="petit avis" style={{ margin: 0 }}>Mode demostració: les dades són inventades.</p>}
          <button type="button" onClick={surt}><Icona nom="surt" />Surt</button>
        </div>
      )}
    </div>
  );
}

export function Shell() {
  const [calaix, setCalaix] = useState(false);
  const loc = useLocation();
  const enllacos = useEnllacos();
  const { usuari } = useSessio();
  const inferior = usuari.rol === 'botiga' ? ['/', '/servei', '/estoc', '/dependent'] : ['/', '/peces', '/origen', '/informes'];

  // En canviar de pàgina, el focus va al títol (lectors de pantalla) i tanquem el calaix.
  const primera = useRef(true);
  useEffect(() => {
    setCalaix(false);
    if (primera.current) { primera.current = false; return; }
    const h = document.getElementById('titol-pagina');
    if (h) h.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [loc.pathname]);

  return (
    <div className="shell">
      <a href="#principal" className="salta">Salta al contingut</a>
      <aside className="barra-lateral">
        <NavLink to="/" className="marca-hebra" aria-label="Hebra, inici"><LogoHebra />Hebra</NavLink>
        <Navegacio />
      </aside>
      <div style={{ minWidth: 0 }}>
        <header className="capcalera">
          <NavLink to="/" className="marca-hebra" aria-label="Hebra, inici"><LogoHebra />Hebra</NavLink>
          <SelectorFiltres />
          <MenuUsuari />
        </header>
        <main id="principal" className="contingut"><Outlet /></main>
      </div>
      <nav className="nav-inferior" aria-label="Navegació principal">
        {inferior.map((a) => enllacos.find((e) => e.a === a)).filter(Boolean).map((e) => (
          <NavLink key={e!.a} to={e!.a} end={e!.a === '/'}><Icona nom={e!.icona} mida={20} />{e!.nom.split(' ')[0]}</NavLink>
        ))}
        <button type="button" className="boto-calaix" aria-expanded={calaix} onClick={() => setCalaix(true)}><Icona nom="mes" mida={20} />Més</button>
      </nav>
      {calaix && (
        <>
          <div className="calaix-fons" onClick={() => setCalaix(false)} aria-hidden="true" />
          <div className="calaix" role="dialog" aria-modal="true" aria-label="Totes les seccions" onKeyDown={(e) => e.key === 'Escape' && setCalaix(false)}>
            <div className="fila entre"><b>Totes les seccions</b><button type="button" className="boto-fantasma" onClick={() => setCalaix(false)} autoFocus>Tanca</button></div>
            <Navegacio enTria={() => setCalaix(false)} />
          </div>
        </>
      )}
    </div>
  );
}
