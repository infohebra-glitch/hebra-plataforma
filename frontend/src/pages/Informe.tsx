/** Un informe com a document: xifres, gràfics (els mateixos que al PDF del servidor), blocs i acció. */
import { useEffect, useState } from 'react';
import { desaBlob } from '../api/client';
import { informes } from '../api/endpoints';
import { DialegCorreu } from '../components/DialegCorreu';
import { GraficInforme } from '../components/grafics/GraficInforme';
import { formatUnitat } from '../lib/escala';
import { EstatEnviament, titolLliurat } from './Informes';
import { Link, useParams } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { BlocInforme, Informe as TInforme, TipusInforme, XifraInforme } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { Icona, LogoHebra } from '../components/Icones';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { ESTATS_DECISIO, INFORMES, motiu, seccio } from '../lib/etiquetes';
import { diaCurt, diaLlarg, enter, eur, pct, punts, segons } from '../lib/format';
import { esDemo } from '../lib/mode';
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
    // Ràtios (p. ex. peticions per sessió): amb decimals, no arrodonides a 0.
    if (!Number.isInteger(v)) return v.toLocaleString('ca-ES', { maximumFractionDigits: 2 });
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
    // Si hi ha el nom del model, el codi sobra; i el «text» llarg ja surt a sobre de la taula.
    const claus = Object.keys(files[0]).filter((k) => !(k === 'model' && 'nom' in files[0]) && k !== 'text');
    return (
      <div className="taula-wrap"><table>
        <thead><tr>{claus.map((k) => <th key={k} scope="col" className={esNumeric(k, files) ? 'n' : undefined}>{nomCamp(k)}</th>)}</tr></thead>
        <tbody>{files.map((f, i) => <tr key={i}>{claus.map((k) => <td key={k} className={esNumeric(k, files) ? 'n' : undefined}>{valorCamp(k, f[k])}</td>)}</tr>)}</tbody>
      </table></div>
    );
  }
  if (dades && typeof dades === 'object' && !Array.isArray(dades)) {
    // Només xifres curtes: els textos llargs ja són al paràgraf del bloc.
    const e = Object.entries(dades as Record<string, unknown>).filter(([k, v]) => (typeof v !== 'object' || v === null) && k !== 'text' && !(typeof v === 'string' && v.length > 40));
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

function Xifres({ xifres }: { xifres: XifraInforme[] }) {
  return (
    <div className="xifres-informe">
      {xifres.map((x) => {
        // La variació de la conversió ve en punts; la resta, en % relatiu.
        // Una variació que s'arrodoneix a 0 es mostra com a neutra («=»), sense signe.
        const cru = x.variacio;
        const v = cru === null || cru === undefined ? null : Math.round(cru * 100) / 100;
        const txt = v === null ? null : v === 0 ? (x.unitat === 'pct' ? 'igual' : '= 0 %') : x.unitat === 'pct' ? punts(v) : `${v > 0 ? '+' : '−'}${pct(Math.abs(v))}`;
        const millor = /temps|perduda/i.test(x.etiqueta) ? (v ?? 0) < 0 : (v ?? 0) > 0;
        const sentit = !v ? 'neutre' : millor ? 'bo' : 'dolent';
        // La fletxa diu cap on es mou la xifra; el color (i el text «millor/pitjor» per a lectors), si és bo o dolent.
        const fletxa = !v ? '' : v > 0 ? '▲' : '▼';
        return (
          <div key={x.etiqueta} className="xifra">
            <span className="xifra-etiqueta">{x.etiqueta}</span>
            <b className="xifra-valor">{formatUnitat(x.valor, x.unitat)}</b>
            {txt && <span className={`rajola-delta ${sentit}`}><span style={{ whiteSpace: 'nowrap' }}><span aria-hidden="true">{fletxa}</span>{txt}</span>{sentit !== 'neutre' && <span className="sr-only"> ({sentit === 'bo' ? 'millor' : 'pitjor'})</span>}<span className="petit muted" style={{ fontWeight: 400 }}> vs {x.vs ?? 'abans'}</span></span>}
          </div>
        );
      })}
    </div>
  );
}

function Document({ inf, botigaId, generat }: { inf: TInforme; botigaId?: string | null; generat?: string }) {
  const { botigues } = useSessio();
  const { filtre } = useFiltre();
  const id = botigaId === undefined ? filtre.botiga : botigaId;
  const botiga = id ? botigues.find((b) => b.id === id)?.nom ?? id : 'Totes les botigues';
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
          {inf.periode.des === inf.periode.fins ? <div>{diaLlarg(inf.periode.des)}</div> : (
            <>
              <div>Del {diaLlarg(inf.periode.des)}</div>
              <div>al {diaLlarg(inf.periode.fins)} ({inf.periode.dies} dies)</div>
            </>
          )}
        </div>
      </header>
      {inf.accio && (
        <div className="accio-doc">
          <b>Acció de la setmana.</b> {inf.accio.text}
          {(inf.accio.responsable || inf.accio.data_limit) && <div className="petit muted">{[inf.accio.responsable, inf.accio.data_limit && `abans del ${diaCurt(inf.accio.data_limit)}`].filter(Boolean).join(' · ')}</div>}
        </div>
      )}
      {inf.xifres && inf.xifres.length > 0 && <Xifres xifres={inf.xifres} />}
      {inf.grafics && inf.grafics.length > 0 && <div className="grafics-informe">{inf.grafics.map((g) => <GraficInforme key={g.id} g={g} />)}</div>}
      {inf.blocs.filter((b) => !(inf.xifres?.length && b.id === 'xifres')).map((b) => <Bloc key={b.id} b={b} />)}
      {inf.avisos.length > 0 && (
        <div className="avisos-doc"><b>Avisos sobre les dades</b><ul>{inf.avisos.map((a, i) => <li key={i}>{a}</li>)}</ul></div>
      )}
      <footer className="peu-doc">
        <span>Només proves de confiança alta i mitjana. Els imports en euros són estimacions.</span>
        <span>Generat el {diaLlarg(generat ?? new Date().toISOString())}</span>
      </footer>
    </article>
  );
}

function Barra({ molla, pdf, envia, inicials, titol, carregat }: { molla: string; pdf: () => Promise<Blob>; envia: (d: string[]) => Promise<unknown>; inicials?: string[]; titol: string; carregat: boolean }) {
  const [correu, setCorreu] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [baixant, setBaixant] = useState(false);
  const descarrega = async () => {
    setError(null); setBaixant(true);
    try { desaBlob(await pdf(), `${titol.replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-+|-+$/g, '').toLowerCase()}.pdf`); } catch (e) { setError((e as Error).message); } finally { setBaixant(false); }
  };
  return (
    <>
      <div className="fila entre no-imprimir" style={{ marginBottom: 16 }}>
        <nav className="molla" aria-label="Molla de pa" style={{ margin: 0 }}><Link to="/informes">Informes</Link> <span aria-hidden="true">›</span> {molla}</nav>
        <div className="fila">
          {!esDemo() && <button type="button" onClick={() => window.print()} disabled={!carregat}><Icona nom="imprimeix" />Imprimeix</button>}
          <button type="button" onClick={() => setCorreu(true)} disabled={!carregat}><Icona nom="correu" />Envia per correu</button>
          <button type="button" className="boto-primari" onClick={descarrega} disabled={!carregat || baixant}><Icona nom="baixa" />{baixant ? 'Preparant…' : 'Descarrega PDF'}</button>
        </div>
      </div>
      {error && <p className="missatge-error no-imprimir" role="alert">No s’ha pogut descarregar el PDF: {error}</p>}
      <DialegCorreu obert={correu} titol={titol} inicial={inicials} enTanca={() => setCorreu(false)} envia={envia} />
    </>
  );
}

/**
 * La marca tria quins gràfics porta aquest informe i en quin ordre. Val per al tauler, el PDF i el correu
 * programat (ho desa el servidor). Sense tria, hi surten tots.
 */
function TriaGrafics({ inf, desa }: { inf: TInforme; desa: (ids: string[] | null) => Promise<void> }) {
  const tots = inf.grafics_disponibles ?? [];
  const inicial = inf.grafics_triats ?? tots.map((g) => g.id);
  const [obert, setObert] = useState(false);
  const [ordre, setOrdre] = useState<string[]>([...inicial, ...tots.map((g) => g.id).filter((i) => !inicial.includes(i))]);
  const [actius, setActius] = useState<Set<string>>(new Set(inicial));
  const [desant, setDesant] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titol = (id: string) => tots.find((g) => g.id === id)?.titol ?? id;
  const mou = (i: number, d: number) => setOrdre((o) => {
    const n = [...o]; const j = i + d; if (j < 0 || j >= n.length) return o; [n[i], n[j]] = [n[j], n[i]]; return n;
  });
  const fes = async (ids: string[] | null) => {
    setError(null); setDesant(true);
    try { await desa(ids); setObert(false); } catch (e) { setError((e as Error).message); } finally { setDesant(false); }
  };
  return (
    <div className="tria-grafics no-imprimir">
      <button type="button" className="boto" aria-expanded={obert} onClick={() => setObert(!obert)}>
        Tria els gràfics ({actius.size} de {tots.length})
      </button>
      {obert && (
        <div className="tria-grafics-panell">
          <p className="petit muted">Marca els gràfics que vols en aquest informe i posa'ls en l'ordre que et va bé.
            Es fa servir al tauler, al PDF i als enviaments programats.</p>
          <ol>
            {ordre.map((id, i) => (
              <li key={id} className={actius.has(id) ? '' : 'apagat'}>
                <label><input type="checkbox" checked={actius.has(id)} onChange={(e) => setActius((a) => {
                  const n = new Set(a); if (e.target.checked) n.add(id); else n.delete(id); return n;
                })} /> {titol(id)}</label>
                <span className="ordre">
                  <button type="button" aria-label={`Puja «${titol(id)}»`} disabled={i === 0} onClick={() => mou(i, -1)}>↑</button>
                  <button type="button" aria-label={`Baixa «${titol(id)}»`} disabled={i === ordre.length - 1} onClick={() => mou(i, 1)}>↓</button>
                </span>
              </li>
            ))}
          </ol>
          {error && <p className="error petit" role="alert">{error}</p>}
          <div className="accions">
            <button type="button" className="boto boto-primari" disabled={desant || actius.size === 0} onClick={() => fes(ordre.filter((i) => actius.has(i)))}>Desa la tria</button>
            <button type="button" className="boto" disabled={desant} onClick={() => fes(null)}>Posa'ls tots</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Informe calculat al moment amb el filtre de dalt (/informes/:tipus). */
export function Informe() {
  const { tipus = 'setmanal' } = useParams();
  const { filtre, clau } = useFiltre();
  const def = INFORMES.find((i) => i.tipus === tipus);
  const q = useApi((s) => analitica.informe(filtre, tipus as TipusInforme, s), [clau, tipus]);
  const { pot } = useSessio();
  if (!def) return <Buit titol="Aquest informe no existeix" accio={<Link to="/informes">Torna als informes</Link>} />;
  return (
    <>
      <Barra molla={def.nom} titol={def.nom} carregat={!!q.dades} pdf={() => informes.pdf(tipus as TipusInforme, filtre)} envia={(d) => informes.envia(tipus as TipusInforme, filtre, d)} />
      {q.dades?.grafics_disponibles && pot('admin', 'marca') && (
        <TriaGrafics key={`${tipus}-${(q.dades.grafics_triats ?? []).join(',')}`} inf={q.dades}
          desa={async (ids) => { await analitica.triaGrafics(filtre, tipus as TipusInforme, ids); q.recarrega(); }} />
      )}
      <Consulta q={q} esquelet={<div className="document"><Esquelet tipus="taula" files={10} /></div>}>
        {(inf) => <Document inf={inf} />}
      </Consulta>
    </>
  );
}

/** Un informe lliurat (instantània guardada): /informes/lliurats/:id. */
export function InformeLliurat() {
  const { id = '' } = useParams();
  const { filtre } = useFiltre();
  const n = Number(id);
  const q = useApi((s) => informes.lliurat(n, s), [n]);
  const llista = useApi((s) => informes.lliurats(filtre.botiga, undefined, s), [filtre.botiga]);
  const l = llista.dades?.lliurats.find((x) => x.id === n);
  const titol = l ? titolLliurat(l) : q.dades?.titol ?? 'Informe';
  return (
    <>
      <Barra molla={titol} titol={titol} carregat={!!q.dades} inicials={l?.enviat_a} pdf={() => informes.pdfLliurat(n)} envia={(d) => informes.enviaLliurat(n, d)} />
      {l && <p className="no-imprimir petit" style={{ margin: '-6px 0 12px' }}><EstatEnviament l={l} /></p>}
      <Consulta q={q} esquelet={<div className="document"><Esquelet tipus="taula" files={10} /></div>}>
        {(inf) => <Document inf={inf} botigaId={l ? l.botiga_id : undefined} generat={l?.generat} />}
      </Consulta>
    </>
  );
}
