/**
 * v0.9: el motiu que dona el client al provador (fitxa NFC) comparat amb el motiu que dona el client
 * online quan torna una peça. Sempre per model i talla, mai per persona.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { analitica, devolucions } from '../api/endpoints';
import type { CategoriaProvadorOnline, CodiDevolucio, MapaDevolucions, ProvadorOnline as TProvadorOnline, SentitTalla } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { Rajola } from '../components/Rajola';
import { Barres } from '../components/grafics/Barres';
import { Columnes } from '../components/grafics/Columnes';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { enter, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

const curt = (nom: string) => nom.replace(/ (o|i) .*$/, '').replace(/^Enviament: .*/, 'Enviament');

export function InsigniaCoincidencia({ c }: { c: number | null }) {
  if (c === null) return <span className="insignia insignia-mostra">Poques dades</span>;
  const classe = c >= 0.7 ? 'insignia-bo' : c >= 0.5 ? 'insignia-neutra' : 'insignia-alerta';
  return <span className={`insignia ${classe}`}>{pct(c)}</span>;
}

function sentit(s: SentitTalla): string {
  const n = s.petita + s.gran;
  if (!n) return '—';
  if (s.petita === s.gran) return `igual (${n})`;
  return s.petita > s.gran ? `petita (${s.petita} de ${n})` : `gran (${s.gran} de ${n})`;
}

/** Les dues distribucions de motius, una al costat de l'altra (també a la fitxa de la peça). */
export function GraficProvadorOnline({ categories, titol }: { categories: CategoriaProvadorOnline[]; titol: string }) {
  return (
    <Columnes titol={titol} x={categories.map((c) => curt(c.nom))} unitat="pct" alcada={220} nomEixX="Motiu"
      series={[{ nom: 'Provador', valors: categories.map((c) => c.pct_provador) }, { nom: 'Online', valors: categories.map((c) => c.pct_online) }]} />
  );
}

export function ProvadorOnline() {
  const { filtre, clau } = useFiltre();
  const [versio, setVersio] = useState(0);
  const q = useApi((s) => analitica.provadorOnline(filtre, s), [clau, versio]);
  const qm = useApi((s) => devolucions.mapa(s), [versio]);
  const torna = () => setVersio((v) => v + 1);
  return (
    <>
      <TitolPagina titol="Provador i online">
        El que diu el client al provador quan no s’emporta una peça, al costat del que diu el client online quan la torna. Si diuen el mateix, el problema és de la peça; si no, potser és de la foto, la descripció o la guia de talles de la web.
      </TitolPagina>
      <Consulta q={q} esquelet={<Esquelet tipus="rajoles" />}>
        {(d) => (d.importat.linies ? <Contingut d={d} /> : <SenseDades />)}
      </Consulta>
      <Consulta q={qm} esquelet={<Esquelet tipus="taula" files={3} />}>
        {(m) => (m.codis.length ? <MapaMotius m={m} enCanvi={torna} /> : null)}
      </Consulta>
      <Privacitat />
    </>
  );
}

function SenseDades() {
  return (
    <div className="panell">
      <Buit titol="Encara no hi ha devolucions online" accio={<Link className="boto-primari" to="/dades#devolucions">Puja el fitxer de devolucions</Link>}>
        Exporta les devolucions de la botiga en línia (Shopify, el teu ERP o un full de càlcul) amb aquestes columnes: <span className="codi">data, gtin, quantitat, motiu</span>, i si vols <span className="codi">comentari</span> i <span className="codi">comanda</span>. Res de noms, correus ni adreces.
      </Buit>
    </div>
  );
}

function Contingut({ d }: { d: TProvadorOnline }) {
  const comparables = d.models.filter((m) => m.coincidencia !== null);
  return (
    <>
      <div className="rajoles">
        <Rajola etiqueta="Coincidència" valor={d.coincidencia === null ? '—' : pct(d.coincidencia)} destacada
          nota={d.coincidencia === null ? `Calen ${d.minim} respostes a cada costat` : '100 % = els mateixos motius als dos llocs'} />
        <Rajola etiqueta="Respostes al provador" valor={enter(d.respostes_provador)} nota="a la fitxa NFC, sense «només mirava»" />
        <Rajola etiqueta="Unitats tornades online" valor={enter(d.devolucions_online)} nota="de tota la botiga en línia" />
        <Rajola etiqueta="Motius que només passen online" valor={pct(d.pct_nomes_online)} nota="foto, defecte, enviament, canvi d’opinió" />
      </div>
      <p className="avis" style={{ marginTop: 16 }}>{d.text}</p>

      <div className="reixa-2">
        <Seccio titol="Per què no se l’emporten i per què la tornen" subtitol="Percentatge sobre les respostes de cada canal, només amb els motius que existeixen als dos llocs.">
          <div className="panell">
            {d.categories.length ? <GraficProvadorOnline categories={d.categories} titol="Motius al provador i online" />
              : <p className="muted">Sense motius comparables en aquest període.</p>}
          </div>
        </Seccio>
        <Seccio titol="Només online" subtitol="Motius de devolució que al provador no poden passar. Si pesen molt, el problema és de la web o de la logística.">
          <div className="panell">
            {d.nomes_online_detall.length
              ? <Barres titol="Motius només online" items={d.nomes_online_detall.map((x) => ({ clau: x.motiu, etiqueta: x.nom, n: x.online, pct: x.pct }))} />
              : <p className="muted">Cap devolució per aquests motius.</p>}
            <p className="petit" style={{ marginTop: 12 }}>
              <b>Talla:</b> online, quan tornen per talla, li va {sentit(d.talla_sentit.online)}. Al provador, quan demanen una altra talla des de la fitxa, la que s’han provat els anava {sentit(d.talla_sentit.provador)}.
            </p>
          </div>
        </Seccio>
      </div>

      <Seccio titol="Peça a peça" subtitol={`Primer les que menys coincideixen. La coincidència només es calcula amb ${d.minim} respostes o més a cada costat.`}>
        <div className="panell" style={{ padding: 0 }}>
          <div className="taula-wrap">
            <table>
              <caption className="sr-only">Motius del provador i de les devolucions online per model</caption>
              <thead><tr>
                <th scope="col">Peça</th><th scope="col" className="n">Provador</th><th scope="col" className="n">Tornades</th>
                <th scope="col">Motiu al provador</th><th scope="col">Motiu online</th><th scope="col" className="n">Coincidència</th>
                <th scope="col">Talla online</th><th scope="col">Què vol dir</th>
              </tr></thead>
              <tbody>
                {d.models.map((m) => (
                  <tr key={m.model}>
                    <td><Link className="nom-model" to={`/peces/${encodeURIComponent(m.model)}`}>{m.nom}</Link></td>
                    <td className="n">{enter(m.respostes_provador)}</td>
                    <td className="n">{enter(m.devolucions_online)}</td>
                    <td>{m.motiu_provador ? d.etiquetes[m.motiu_provador] ?? m.motiu_provador : '—'}</td>
                    <td>{m.motiu_online ? d.etiquetes[m.motiu_online] ?? m.motiu_online : '—'}</td>
                    <td className="n"><InsigniaCoincidencia c={m.coincidencia} /></td>
                    <td>{sentit(m.talla_online)}</td>
                    <td className="petit">{m.lectura}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!comparables.length && <p className="petit muted" style={{ padding: '8px 12px 12px', margin: 0 }}>Encara cap peça té prou respostes als dos llocs per comparar-les.</p>}
        </div>
      </Seccio>

      {d.talles.length > 0 && (
        <Seccio titol="Devolucions per talla" subtitol="Unitats tornades online pel motiu «talla», per peça i talla: si una talla sempre va petita, és el patró d’aquesta talla.">
          <div className="panell" style={{ padding: 0 }}>
            <div className="taula-wrap">
              <table>
                <caption className="sr-only">Devolucions per talla</caption>
                <thead><tr><th scope="col">Peça</th><th scope="col">Talla</th><th scope="col" className="n">Massa petita</th><th scope="col" className="n">Massa gran</th><th scope="col" className="n">Sense dir</th></tr></thead>
                <tbody>
                  {d.talles.map((t) => (
                    <tr key={`${t.model}-${t.talla}`}>
                      <td>{t.nom}</td><td><b>{t.talla ?? '—'}</b></td>
                      <td className="n">{enter(t.petita)}</td><td className="n">{enter(t.gran)}</td><td className="n">{enter(t.sense)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Seccio>
      )}
    </>
  );
}

function FilaCodi({ c, m, enCanvi }: { c: CodiDevolucio; m: MapaDevolucions; enCanvi: () => void }) {
  const [desant, setDesant] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valor = c.motiu === 'talla' && c.sentit ? `talla:${c.sentit}` : c.motiu;
  const canvia = async (v: string) => {
    const [motiu, s] = v.split(':');
    setDesant(true); setError(null);
    try { await devolucions.desaMapa(c.codi, motiu, (s as 'petita' | 'gran') ?? null); enCanvi(); } catch (e) { setError((e as Error).message); } finally { setDesant(false); }
  };
  const id = `mapa-${c.codi}`;
  return (
    <tr>
      <td><label htmlFor={id} className="codi">{c.codi}</label></td>
      <td className="n">{enter(c.unitats)}</td>
      <td>
        <select id={id} value={valor} disabled={desant} onChange={(e) => canvia(e.target.value)}>
          {m.categories.map((k) => k.clau === 'talla' ? [
            <option key="talla" value="talla">Talla</option>,
            <option key="talla:petita" value="talla:petita">Talla: massa petita</option>,
            <option key="talla:gran" value="talla:gran">Talla: massa gran</option>,
          ] : <option key={k.clau} value={k.clau}>{k.nom}{k.nomes_online ? ' (només online)' : ''}</option>)}
        </select>
        {error && <p className="missatge-error" role="alert">{error}</p>}
      </td>
      <td>{c.manual ? <span className="insignia insignia-marca">Triat per la marca</span> : <span className="insignia insignia-neutra">Automàtic</span>}</td>
    </tr>
  );
}

function MapaMotius({ m, enCanvi }: { m: MapaDevolucions; enCanvi: () => void }) {
  return (
    <Seccio titol="Com llegim els motius de la teva botiga en línia" subtitol="Cada botiga en línia té els seus codis. Hebra els tradueix sola a les categories del provador; si n’hi ha cap de mal posat, canvia’l aquí i tota la comparativa es recalcula.">
      <div className="panell" style={{ padding: 0 }}>
        <div className="taula-wrap">
          <table>
            <caption className="sr-only">Traducció dels motius de devolució</caption>
            <thead><tr><th scope="col">Motiu al fitxer</th><th scope="col" className="n">Unitats</th><th scope="col">Categoria a Hebra</th><th scope="col">Com s’ha triat</th></tr></thead>
            <tbody>{m.codis.map((c) => <FilaCodi key={c.codi} c={c} m={m} enCanvi={enCanvi} />)}</tbody>
          </table>
        </div>
        <p className="petit muted" style={{ padding: '8px 12px 12px', margin: 0 }}>
          {enter(m.importat.linies)} línies importades{m.importat.des ? <>, del {m.importat.des} al {m.importat.fins}</> : null}.
        </p>
      </div>
    </Seccio>
  );
}

function Privacitat() {
  return (
    <Seccio titol="Què es fa servir i què no" subtitol="Per a la marca, el seu delegat de protecció de dades o qui ho pregunti.">
      <div className="panell">
        <ul className="petit" style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6 }}>
          <li>No s’uneix mai una persona del provador amb un client online. La comparació és per peça, talla i període, sempre amb totals.</li>
          <li>Del fitxer de devolucions només es desen la data, el GTIN, les unitats i el motiu. Si porta columnes com correu, nom, adreça o telèfon, s’ignoren i Hebra avisa.</li>
          <li>El comentari lliure del client, si n’hi ha, es llegeix per endevinar-ne el motiu i es llença: no es desa enlloc.</li>
          <li>El número de comanda només serveix per no comptar dues vegades la mateixa línia; es desa com una empremta xifrada, mai en clar.</li>
          <li>Les dades són de la marca i es queden a la seva instal·lació. Es poden esborrar totes des de «Connexions i dades».</li>
        </ul>
      </div>
    </Seccio>
  );
}
