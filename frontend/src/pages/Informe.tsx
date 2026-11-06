/** Un informe com a document net d'una pàgina. «Desa en PDF» obre el diàleg d'impressió del navegador. */
import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { BlocInforme, Informe as TInforme, TipusInforme } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { Icona, LogoHebra } from '../components/Icones';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { ESTATS_DECISIO, INFORMES, motiu, seccio } from '../lib/etiquetes';
import { diaCurt, diaLlarg, enter, eur, pct, punts, segons } from '../lib/format';
import { useApi } from '../lib/useApi';

const NOMS: Record<string, string> = {
  proves: 'Proves', compres: 'Compres', conversio: 'Conversió', conversio_categoria: 'Conversió de la categoria', variacio_conversio: 'Variació de la conversió',
  conversio_resta_talles: 'Resta de talles', model: 'Model', nom: 'Model', talla: 'Talla', color: 'Color', categoria: 'Categoria', peticions: 'Peticions',
  motiu: 'Motiu', respostes: 'Respostes', pct: '%', n: 'Nombre', mediana_s: 'Temps de resposta (mediana)', pct_sota_90s: 'Per sota de 90 s',
  decisio: 'Decisió', estat: 'Estat', resultat: 'Resultat', unitats: 'Unitats', dies: 'Dies sense activitat', palanca: 'Palanca',
  valor_eur: 'Valor (estimació)', detall: 'Detall', grup: 'Grup', criteri: 'Criteri', objectiu: 'Objectiu', compleix: 'Compleix', pais: 'País', seccio: 'Secció',
};
const nomCamp = (k: string) => NOMS[k] ?? k.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

function valorCamp(k: string, v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') {
    if (/^variacio|^diferencia/.test(k)) return punts(v);
    if (/conversio|^pct|taxa/.test(k)) return pct(v);
    if (/_eur$|^preu/.test(k)) return eur(v);
    if (/_s$/.test(k)) return segons(v);
    return enter(v);
  }
  if (typeof v === 'string') {
    if (k === 'motiu') return motiu(v);
    if (k === 'seccio') return seccio(v);
    if (k === 'estat' && v in ESTATS_DECISIO) return ESTATS_DECISIO[v as keyof typeof ESTATS_DECISIO];
    return v;
  }
  if (typeof v === 'boolean') return v ? 'Sí' : 'No';
  return '';
}

const esNumeric = (k: string, files: Record<string, unknown>[]) => files.every((f) => typeof f[k] === 'number' || f[k] === null);

function DadesBloc({ dades }: { dades: unknown }) {
  if (Array.isArray(dades) && dades.length && typeof dades[0] === 'object' && dades[0] !== null) {
    const files = dades as Record<string, unknown>[];
    const claus = Object.keys(files[0]);
    return (
      <div className="taula-wrap"><table>
        <thead><tr>{claus.map((k) => <th key={k} scope="col" className={esNumeric(k, files) ? 'n' : undefined}>{nomCamp(k)}</th>)}</tr></thead>
        <tbody>{files.map((f, i) => <tr key={i}>{claus.map((k) => <td key={k} className={esNumeric(k, files) ? 'n' : undefined}>{valorCamp(k, f[k])}</td>)}</tr>)}</tbody>
      </table></div>
    );
  }
  if (dades && typeof dades === 'object' && !Array.isArray(dades)) {
    const e = Object.entries(dades as Record<string, unknown>).filter(([, v]) => typeof v !== 'object' || v === null);
    if (!e.length) return null;
    return <div className="xifres-doc">{e.map(([k, v]) => <div key={k}><b>{valorCamp(k, v)}</b>{nomCamp(k)}</div>)}</div>;
  }
  return null;
}

function Bloc({ b }: { b: BlocInforme }) {
  return (
    <section className="bloc" aria-labelledby={`bloc-${b.id}`}>
      <h2 id={`bloc-${b.id}`}>{b.titol}</h2>
      {b.text && <p>{b.text}</p>}
      <DadesBloc dades={b.dades} />
    </section>
  );
}

function Document({ inf }: { inf: TInforme }) {
  const { botigues } = useSessio();
  const { filtre } = useFiltre();
  const botiga = filtre.botiga ? botigues.find((b) => b.id === filtre.botiga)?.nom ?? filtre.botiga : 'Totes les botigues';
  useEffect(() => { document.title = `${inf.titol} · ${diaCurt(inf.periode.des)}–${diaCurt(inf.periode.fins)} · Hebra`; }, [inf]);
  return (
    <article className="document">
      <header className="document-cap">
        <div>
          <span className="marca-hebra"><LogoHebra />Hebra</span>
          <h1 id="titol-pagina" tabIndex={-1}>{inf.titol}</h1>
        </div>
        <div className="periode">
          <div><b>{botiga}</b></div>
          <div>Del {diaLlarg(inf.periode.des)}</div>
          <div>al {diaLlarg(inf.periode.fins)} ({inf.periode.dies} dies)</div>
        </div>
      </header>
      {inf.accio && (
        <div className="accio-doc">
          <b>Acció de la setmana.</b> {inf.accio.text}
          {(inf.accio.responsable || inf.accio.data_limit) && <div className="petit muted">{[inf.accio.responsable, inf.accio.data_limit && `abans del ${diaCurt(inf.accio.data_limit)}`].filter(Boolean).join(' · ')}</div>}
        </div>
      )}
      {inf.blocs.map((b) => <Bloc key={b.id} b={b} />)}
      {inf.avisos.length > 0 && (
        <div className="avisos-doc"><b>Avisos sobre les dades</b><ul>{inf.avisos.map((a, i) => <li key={i}>{a}</li>)}</ul></div>
      )}
      <footer className="peu-doc">
        <span>Només proves de confiança alta i mitjana. Els imports en euros són estimacions.</span>
        <span>Generat el {diaLlarg(new Date().toISOString())}</span>
      </footer>
    </article>
  );
}

export function Informe() {
  const { tipus = 'setmanal' } = useParams();
  const { filtre, clau } = useFiltre();
  const def = INFORMES.find((i) => i.tipus === tipus);
  const q = useApi((s) => analitica.informe(filtre, tipus as TipusInforme, s), [clau, tipus]);
  if (!def) return <Buit titol="Aquest informe no existeix" accio={<Link to="/informes">Torna als informes</Link>} />;
  return (
    <>
      <div className="fila entre no-imprimir" style={{ marginBottom: 16 }}>
        <nav className="molla" aria-label="Molla de pa" style={{ margin: 0 }}><Link to="/informes">Informes</Link> <span aria-hidden="true">›</span> {def.nom}</nav>
        <button type="button" className="boto-primari" onClick={() => window.print()} disabled={!q.dades}><Icona nom="imprimeix" />Desa en PDF</button>
      </div>
      <Consulta q={q} esquelet={<div className="document"><Esquelet tipus="taula" files={10} /></div>}>
        {(inf) => <Document inf={inf} />}
      </Consulta>
    </>
  );
}
