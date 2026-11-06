import { Link, useParams } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { ModelDetall } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { TargetaExperiment } from '../components/Experiment';
import { MostraPetita } from '../components/Insignies';
import { Rajola } from '../components/Rajola';
import { Barres } from '../components/grafics/Barres';
import { CorbaTalles } from '../components/grafics/CorbaTalles';
import { SerieTemporal } from '../components/grafics/SerieTemporal';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { motiu } from '../lib/etiquetes';
import { deCada, diaCurt, enter, eur, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

export function PecaDetall() {
  const { model = '' } = useParams();
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.model(filtre, model, s), [clau, model]);
  return (
    <>
      <nav className="molla" aria-label="Molla de pa"><Link to="/peces">Peces</Link> <span aria-hidden="true">›</span> {q.dades?.nom ?? model}</nav>
      <Consulta q={q} esquelet={<><Esquelet tipus="rajoles" /><div style={{ height: 16 }} /><Esquelet tipus="taula" /></>}>
        {(d) => <Detall d={d} />}
      </Consulta>
    </>
  );
}

function Detall({ d }: { d: ModelDetall }) {
  const k = d.kpi;
  return (
    <>
      <TitolPagina titol={d.nom}>{d.model} · {d.categoria} · {d.color} · {eur(d.preu)}</TitolPagina>
      <div className="rajoles">
        <Rajola etiqueta="Proves" valor={enter(k.proves)} />
        <Rajola etiqueta="Conversió" valor={pct(k.conversio)} nota={<>{deCada(k.compres, k.proves)} proves acaben en compra</>} insignia={<MostraPetita n={k.proves} />} />
        <Rajola etiqueta="Venut sense provar" valor={enter(k.venut_sense_provar)} nota="unitats venudes sense passar per la cabina" />
        <Rajola etiqueta="Respostes de motiu" valor={enter(k.respostes_motiu)} nota={<>taxa de resposta del {pct(k.taxa_resposta_motiu)}</>} />
      </div>

      <Seccio titol="Talles: provat contra comprat" subtitol="Si una talla es prova molt més del que es compra, el patró d’aquesta talla pot no quadrar.">
        <div className="pila">
          <div className="panell">
            {d.talles.length ? <CorbaTalles titol={`Corba de talles de ${d.nom}`} files={d.talles} /> : <p className="muted">Sense proves per talla.</p>}
          </div>
          <div className="panell" style={{ padding: 0 }}>
            <div className="taula-wrap">
              <table>
                <caption className="sr-only">Proves i compres per talla</caption>
                <thead><tr><th scope="col">Talla</th><th scope="col" className="n">Proves</th><th scope="col" className="n">Compres</th><th scope="col" className="n">Conversió</th><th scope="col" className="n">% provat</th><th scope="col" className="n">% comprat</th><th scope="col" className="n">Estoc</th><th scope="col" className="n">Perduda</th></tr></thead>
                <tbody>
                  {d.talles.map((t) => (
                    <tr key={t.talla}>
                      <td><b>{t.talla}</b></td>
                      <td className="n">{enter(t.proves)}</td>
                      <td className="n">{enter(t.compres)}</td>
                      <td className="n"><span style={{ display: 'inline-grid', justifyItems: 'end', gap: 2 }}>{pct(t.conversio)}<MostraPetita n={t.proves} /></span></td>
                      <td className="n">{pct(t.pct_proves)}</td>
                      <td className="n">{pct(t.pct_compres)}</td>
                      <td className="n">{t.estoc === 0 ? <span className="insignia insignia-critic">0</span> : enter(t.estoc)}</td>
                      <td className="n">{enter(t.demanda_perduda)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="petit muted" style={{ padding: '8px 12px 12px', margin: 0 }}>«Perduda»: peticions d’aquesta talla quan no n’hi havia a la botiga.</p>
          </div>
        </div>
      </Seccio>

      <div className="reixa-2">
        <Seccio titol="Per què no se l’emporten" subtitol={<>{enter(k.respostes_motiu)} respostes a la fitxa NFC (taxa de resposta del {pct(k.taxa_resposta_motiu)}). Només responen alguns clients: és una pista, no un cens.</>}>
          <div className="panell">
            {d.motius.length ? <Barres titol="Motius de no compra" items={d.motius.map((m) => ({ clau: m.motiu, etiqueta: motiu(m.motiu), n: m.n, pct: m.pct }))} /> : <Buit titol="Encara cap resposta">Quan algú digui a la fitxa per què no se l’emporta, apareixerà aquí.</Buit>}
          </div>
        </Seccio>
        <Seccio titol="Tendència setmanal" subtitol="Conversió de les darreres setmanes.">
          <div className="panell">
            <SerieTemporal
              titol={`Conversió setmanal de ${d.nom}`}
              x={d.serie_setmanal.map((s) => s.setmana)}
              etiquetaX={(i) => diaCurt(d.serie_setmanal[i].setmana)}
              detallX={(i) => `Setmana del ${diaCurt(d.serie_setmanal[i].setmana)}`}
              series={[{ clau: 'conversio', nom: 'Conversió', classe: 's1', valors: d.serie_setmanal.map((s) => s.conversio) }]}
              formatY={(n) => pct(n)}
              formatValor={(v, _s, i) => (v === null ? '—' : `${pct(v)} (${deCada(d.serie_setmanal[i].compres, d.serie_setmanal[i].proves)})`)}
              alcada={200}
            />
          </div>
        </Seccio>
      </div>

      <div className="reixa-2">
        <Seccio titol="Es prova amb" subtitol="Peces que entren a la mateixa cabina, a la mateixa sessió.">
          <div className="panell">
            {d.provat_amb.length ? (
              <ul className="barres">
                {d.provat_amb.map((p) => (
                  <li key={p.model} style={{ gridTemplateColumns: '1fr auto' }}>
                    <Link to={`/peces/${encodeURIComponent(p.model)}`}>{p.nom}</Link>
                    <span className="valor">{enter(p.sessions)} sessions</span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">Encara no es prova amb cap altra peça.</p>}
          </div>
        </Seccio>
        <Seccio titol="D’on ve" subtitol="El recorregut que la fitxa NFC ensenya els dies «amb origen».">
          <div className="panell">
            {d.origen ? (
              <>
                <ol className="etapes-origen">
                  {d.origen.etapes.map((e, i) => <li key={i}><b>{e.etapa}</b><br /><span className="muted">{e.regio}, {e.pais}</span></li>)}
                </ol>
                <p className="petit" style={{ marginTop: 8 }}><b>Composició:</b> {d.origen.composicio.map((c) => `${pct(c.pct)} ${c.material.toLowerCase()} (${c.pais})`).join(', ')}</p>
              </>
            ) : <p className="muted">Aquest model encara no té fitxa d’origen. Es pot afegir des del catàleg.</p>}
          </div>
        </Seccio>
      </div>

      {d.efecte_origen && (
        <Seccio titol="L’origen fa vendre aquesta peça?" subtitol={`Resultats de la prova ${d.efecte_origen.id} només per a aquest model, des del ${diaCurt(d.efecte_origen.inici)}`}>
          <TargetaExperiment e={d.efecte_origen} compacta />
        </Seccio>
      )}
    </>
  );
}
