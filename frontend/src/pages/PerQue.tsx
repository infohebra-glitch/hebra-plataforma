import { Link } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { Motiu } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { Rajola } from '../components/Rajola';
import { Barres } from '../components/grafics/Barres';
import { MapaCalor } from '../components/grafics/MapaCalor';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { MOTIUS, motiu } from '../lib/etiquetes';
import { enter, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

export function PerQue() {
  const { filtre, clau } = useFiltre();
  const qm = useApi((s) => analitica.motius(filtre, s), [clau]);
  const qd = useApi((s) => analitica.demandaPerduda(filtre, s), [clau]);
  return (
    <>
      <TitolPagina titol="Per què no compren">El que diuen els clients a la fitxa NFC quan no s’emporten la peça, i les talles que volien i no hi eren.</TitolPagina>
      <Consulta q={qm} esquelet={<Esquelet tipus="rajoles" />}>
        {(m) => (
          <>
            <div className="rajoles">
              <Rajola etiqueta="Respostes" valor={enter(m.respostes)} nota={<>de {enter(m.sessions_fitxa)} sessions amb la fitxa oberta</>} />
              <Rajola etiqueta="Taxa de resposta" valor={pct(m.taxa_resposta)} nota="Responen pocs clients: llegeix-ho com una pista" />
              <Rajola etiqueta="Motiu més citat" valor={m.per_motiu[0] ? motiu(m.per_motiu[0].motiu) : '—'} nota={m.per_motiu[0] ? <>{enter(m.per_motiu[0].n)} respostes ({pct(m.per_motiu[0].pct)})</> : 'Sense respostes'} />
            </div>
            <div className="reixa-2">
              <Seccio titol="Motius de no compra" subtitol={`Percentatge sobre ${enter(m.respostes)} respostes.`}>
                <div className="panell">
                  {m.per_motiu.length ? <Barres titol="Motius" items={m.per_motiu.map((x) => ({ clau: x.motiu, etiqueta: motiu(x.motiu), n: x.n, pct: x.pct }))} />
                    : <Buit titol="Encara cap resposta">Quan algú digui a la fitxa per què no s’emporta una peça, ho veuràs aquí.</Buit>}
                </div>
              </Seccio>
              <Seccio titol="Per model" subtitol="Nombre de respostes de cada motiu. Com més fosc, més respostes.">
                <div className="panell">
                  {m.per_model.length ? (
                    <MapaCalor
                      titol="Motius per model"
                      capFila="Model"
                      files={m.per_model.map((x) => ({ clau: x.model, nom: <Link to={`/peces/${encodeURIComponent(x.model)}`}>{x.nom}</Link> }))}
                      columnes={(Object.keys(MOTIUS) as Motiu[]).map((k) => ({ clau: k, nom: MOTIUS[k].split(' ')[0] }))}
                      llegendaEscala={['menys', 'més respostes']}
                      cel={(mod, mot) => {
                        const fila = m.per_model.find((x) => x.model === mod)!;
                        const n = fila.motius[mot as Motiu] ?? 0;
                        return { v: n, text: n ? enter(n) : '·', titol: `${fila.nom}: ${n} de ${fila.respostes} respostes diuen «${motiu(mot)}»` };
                      }}
                    />
                  ) : <p className="muted">Sense respostes per model.</p>}
                </div>
              </Seccio>
            </div>
          </>
        )}
      </Consulta>
      <Seccio titol="Demanda perduda" subtitol="Peticions de talla o color fetes des de la fitxa quan no n’hi havia a la botiga.">
        <Consulta q={qd} esquelet={<Esquelet tipus="taula" files={4} />}>
          {(d) => d.per_variant.length ? (
            <div className="panell" style={{ padding: 0 }}>
              <p style={{ padding: '14px 16px 0' }}>{d.text}</p>
              <div className="taula-wrap">
                <table>
                  <caption className="sr-only">Demanda perduda per variant</caption>
                  <thead><tr><th scope="col">Model</th><th scope="col">Color</th><th scope="col">Talla</th><th scope="col" className="n">Peticions</th><th scope="col" className="n">Estoc ara</th></tr></thead>
                  <tbody>
                    {d.per_variant.map((v) => (
                      <tr key={`${v.model}-${v.color}-${v.talla}`}>
                        <td><Link className="nom-model" to={`/peces/${encodeURIComponent(v.model)}`}>{v.nom}</Link></td>
                        <td>{v.color}</td><td><b>{v.talla}</b></td><td className="n">{enter(v.n)}</td>
                        <td className="n">{v.estoc === 0 ? <span className="insignia insignia-critic">0</span> : enter(v.estoc)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot><tr><th scope="row" colSpan={3}>Total</th><td className="n"><b>{enter(d.total)}</b></td><td /></tr></tfoot>
                </table>
              </div>
            </div>
          ) : <div className="panell"><Buit titol="Cap talla demanada que no hi fos">En aquest període, cada petició de talla tenia estoc a la botiga.</Buit></div>}
        </Consulta>
      </Seccio>
    </>
  );
}
