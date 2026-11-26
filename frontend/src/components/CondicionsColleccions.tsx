/**
 * Condicions del dia (pluja, festiu, rebaixes...) i col·leccions de la marca, per poder filtrar i comparar
 * «Proves i compres per dia». De moment es marquen a mà; la meteorologia es podrà omplir sola més endavant.
 */
import { useState, type FormEvent } from 'react';
import { analitica } from '../api/endpoints';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { diaLlarg } from '../lib/format';
import { useApi } from '../lib/useApi';

const SUGGERIDES = ['pluja', 'calor', 'fred', 'festiu', 'rebaixes', 'esdeveniment'];

export function CondicionsDia() {
  const { filtre } = useFiltre();
  const q = useApi((s) => analitica.condicions(filtre.botiga, s), [filtre.botiga]);
  const [data, setData] = useState('');
  const [condicio, setCondicio] = useState('pluja');
  const [error, setError] = useState<string | null>(null);
  const afegeix = async (e: FormEvent) => {
    e.preventDefault(); setError(null);
    try { await analitica.novaCondicio({ botiga_id: filtre.botiga, data, condicio }); setData(''); q.recarrega(); } catch (x) { setError((x as Error).message); }
  };
  const treu = async (d: string, c: string) => { await analitica.esborraCondicio(d, c, filtre.botiga); q.recarrega(); };
  // Un dia per fila, amb les seves condicions al costat (els més recents primer).
  const perDia = new Map<string, Set<string>>();
  for (const f of q.dades ?? []) { if (!perDia.has(f.data)) perDia.set(f.data, new Set()); perDia.get(f.data)!.add(f.condicio); }
  const dies = [...perDia.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  const [totes, setTotes] = useState(false);
  return (
    <div className="panell">
      <h3>Condicions del dia</h3>
      <p className="petit muted">Marca els dies especials perquè els puguis filtrar a «Proves i compres per dia». {filtre.botiga ? 'S’aplica a la botiga triada a dalt.' : 'Sense botiga triada, s’aplica a totes.'} Més endavant la pluja i la temperatura es podran omplir soles.</p>
      <form className="fila-form" onSubmit={afegeix}>
        <label>Dia <input type="date" required value={data} onChange={(e) => setData(e.target.value)} /></label>
        <label>Condició
          <input list="condicions-suggerides" required maxLength={30} value={condicio} onChange={(e) => setCondicio(e.target.value)} />
          <datalist id="condicions-suggerides">{SUGGERIDES.map((s) => <option key={s} value={s} />)}</datalist>
        </label>
        <button className="boto boto-primari" type="submit">Afegeix</button>
      </form>
      {error && <p className="error petit" role="alert">{error}</p>}
      {dies.length ? (
        <>
          <ul className="llista-simple dies-marcats">{dies.slice(0, totes ? 400 : 10).map(([d, cs]) => (
            <li key={d}><span>{diaLlarg(d)}</span>
              <span className="xips">{[...cs].map((c) => (
                <span key={c} className="xip">{c}
                  <button type="button" onClick={() => treu(d, c)} aria-label={`Treu ${c} del ${diaLlarg(d)}`}>×</button></span>
              ))}</span></li>
          ))}</ul>
          {dies.length > 10 && <button type="button" className="boto" style={{ marginTop: 8 }} onClick={() => setTotes(!totes)}>{totes ? 'Mostra’n menys' : `Mostra’ls tots (${dies.length})`}</button>}
        </>
      ) : <p className="petit muted">Encara no hi ha cap dia marcat.</p>}
    </div>
  );
}

export function Colleccions() {
  const { pot } = useSessio();
  const q = useApi((s) => analitica.colleccions(s), []);
  const [nom, setNom] = useState('');
  const [des, setDes] = useState('');
  const [fins, setFins] = useState('');
  const [error, setError] = useState<string | null>(null);
  if (!pot('admin', 'marca')) return null;
  const afegeix = async (e: FormEvent) => {
    e.preventDefault(); setError(null);
    try { await analitica.novaColleccio({ nom, des, fins }); setNom(''); setDes(''); setFins(''); q.recarrega(); } catch (x) { setError((x as Error).message); }
  };
  return (
    <div className="panell">
      <h3>Col·leccions</h3>
      <p className="petit muted">Les dates de cada col·lecció o temporada, per comparar-ne una amb una altra dia a dia.</p>
      <form className="fila-form" onSubmit={afegeix}>
        <label>Nom <input required maxLength={60} value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Primavera-estiu 2026" /></label>
        <label>Des de <input type="date" required value={des} onChange={(e) => setDes(e.target.value)} /></label>
        <label>Fins a <input type="date" required value={fins} onChange={(e) => setFins(e.target.value)} /></label>
        <button className="boto boto-primari" type="submit">Afegeix</button>
      </form>
      {error && <p className="error petit" role="alert">{error}</p>}
      {q.dades?.length ? (
        <ul className="llista-simple">{q.dades.map((c) => (
          <li key={c.id}><span><b>{c.nom}</b> · {diaLlarg(c.des)} – {diaLlarg(c.fins)}</span>
            <button type="button" className="boto" onClick={async () => { await analitica.esborraColleccio(c.id); q.recarrega(); }}>Esborra</button></li>
        ))}</ul>
      ) : <p className="petit muted">Encara no hi ha cap col·lecció.</p>}
    </div>
  );
}
