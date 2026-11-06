/** Sessions de provador (C): quantes peces s'hi proven, què es prova junt i el dubte de talla. */
import { Link } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { Sessions as TSessions } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { EXPLICACIO_DUBTE, TaulaParells, llegendaCompra } from '../components/DubteTalla';
import { Rajola } from '../components/Rajola';
import { Columnes } from '../components/grafics/Columnes';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { liftEnParaules } from '../lib/escala';
import { decimal, enter, pct, segons } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useState } from 'react';

/** Primer els parells amb prou sessions per dir-ne res (≥ 3); la resta, a demanda. */
function ParellsTalla({ parells }: { parells: TSessions['mateix_model_diferent_talla']['parells_talla'] }) {
  const [tots, setTots] = useState(false);
  const rellevants = parells.filter((p) => p.sessions >= 3);
  const visibles = tots || !rellevants.length ? parells : rellevants;
  return (
    <>
      <TaulaParells parells={visibles} ambModel />
      {visibles.length < parells.length && (
        <p className="petit" style={{ padding: '0 14px 12px' }}>
          <button type="button" className="enllac" onClick={() => setTots(true)}>Mostra també els {parells.length - visibles.length} parells amb menys de 3 sessions</button>
        </p>
      )}
    </>
  );
}

const Petita = ({ si }: { si?: boolean }) => (si ? <span className="insignia insignia-mostra" title="Menys de 10 sessions: el percentatge pot canviar molt">Mostra petita</span> : null);

export function Sessions() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.sessions(filtre, s), [clau]);
  return (
    <>
      <TitolPagina titol="Sessions de provador">Una sessió és cada vegada que algú entra a una cabina amb peces. Aquí veus quantes s’hi emporta, quines es proven juntes i quan dubten de talla.</TitolPagina>
      <Consulta q={q} esquelet={<><Esquelet tipus="rajoles" /><div style={{ height: 16 }} /><Esquelet tipus="grafic" /></>}>
        {(d) => (d.kpi.sessions ? <Cos d={d} /> : <div className="panell"><Buit titol="Cap sessió en aquest període">Quan les cabines enviïn dades, aquí sortiran les sessions.</Buit></div>)}
      </Consulta>
    </>
  );
}

function Cos({ d }: { d: TSessions }) {
  const k = d.kpi;
  const ppp = d.per_nombre_peces;
  const millor = [...ppp].sort((a, b) => (b.conversio_sessio ?? 0) - (a.conversio_sessio ?? 0))[0];
  const dubte = d.mateix_model_diferent_talla;
  return (
    <>
      <div className="rajoles">
        <Rajola etiqueta="Sessions" valor={enter(k.sessions)} nota="entrades a cabina amb alguna prova vàlida" />
        <Rajola etiqueta="Peces per sessió" valor={decimal(k.peces_per_sessio_mitjana)} nota={<>de mitjana · la meitat de les sessions en porten {enter(k.peces_per_sessio_mediana)} o menys</>} />
        <Rajola etiqueta="Durada d’una sessió" valor={segons(k.durada_mitjana_s)} nota="mitjana, de porta tancada a porta oberta" />
        <Rajola etiqueta="Sessions amb compra" valor={pct(k.pct_sessions_amb_compra)} nota="alguna peça provada s’ha acabat venent" />
      </div>

      <Seccio titol="Segons quantes peces s’hi emporten" subtitol={millor ? <>Les sessions amb {millor.peces === '5+' ? '5 peces o més' : `${millor.peces} ${millor.peces === '1' ? 'peça' : 'peces'}`} són les que acaben més sovint en compra ({pct(millor.conversio_sessio)}). Si n’hi ha moltes d’una sola peça, potser val la pena proposar-ne una altra per combinar.</> : null}>
        <div className="panell">
          <Columnes titol="Sessions segons el nombre de peces" nomEixX="Peces a la cabina" x={ppp.map((p) => (p.peces === '1' ? '1 peça' : `${p.peces} peces`))}
            series={[{ nom: 'Sessions', valors: ppp.map((p) => p.sessions) }]}
            subetiquetes={ppp.map((p) => `${pct(p.conversio_sessio)} compren`)} alcada={230} />
          <p className="petit muted" style={{ margin: '8px 0 0' }}>La columna diu quantes sessions; a sota, quina part d’aquestes sessions ha acabat amb alguna compra.{ppp.some((p) => p.mostra_petita) && ' Alguna columna té menys de 10 sessions: mira-la amb prudència.'}</p>
        </div>
      </Seccio>

      <Seccio titol="Peces que es proven juntes" subtitol="Parells de models que entren a la mateixa cabina a la mateixa sessió (com a mínim 3 sessions). Serveix per decidir què posar a prop a la botiga i què proposar a la fitxa a «Combina amb».">
        <div className="panell" style={{ padding: 0 }}>
          {d.provades_juntes.length ? (
            <div className="taula-wrap"><table>
              <caption className="sr-only">Models provats junts</caption>
              <thead><tr><th scope="col">Parell</th><th scope="col" className="n">Sessions</th><th scope="col">Com de sovint, comparat amb l’atzar</th><th scope="col" className="n">Compren alguna</th></tr></thead>
              <tbody>{d.provades_juntes.map((p) => (
                <tr key={p.model_a + p.model_b}>
                  <td><Link className="nom-model" to={`/peces/${encodeURIComponent(p.model_a)}`}>{p.nom_a}</Link> <span className="muted">+</span> <Link className="nom-model" to={`/peces/${encodeURIComponent(p.model_b)}`}>{p.nom_b}</Link></td>
                  <td className="n">{enter(p.sessions)} <Petita si={p.mostra_petita} /></td>
                  <td><span className="lift"><b>{p.lift === null ? '—' : `× ${decimal(p.lift)}`}</b> <span className="petit muted">{liftEnParaules(p.lift)}</span></span></td>
                  <td className="n">{pct(p.conversio_conjunta)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <Buit titol="Encara cap parell">Calen com a mínim 3 sessions amb els mateixos dos models.</Buit>}
          <p className="petit muted" style={{ margin: 0, padding: '8px 12px 12px' }}>«× 2,0» vol dir que aquestes dues peces coincideixen a la cabina el doble de vegades del que passaria si cada client agafés peces a l’atzar. «Compren alguna»: sessions amb aquest parell on s’ha venut alguna de les dues.</p>
        </div>
      </Seccio>

      <Seccio titol="Dubte de talla" subtitol={<>{enter(dubte.sessions)} sessions ({pct(dubte.pct_sessions)} del total) s’han emportat la mateixa peça en dues talles o més. {EXPLICACIO_DUBTE}</>}>
        <div className="pila">
          <div className="panell" style={{ padding: 0 }}>
            <h3 style={{ padding: '14px 14px 0' }}>Models amb més dubte</h3>
            <div className="taula-wrap"><table>
              <caption className="sr-only">Dubte de talla per model</caption>
              <thead><tr><th scope="col">Model</th><th scope="col" className="n">Sessions amb dubte</th><th scope="col" className="n">De les seves sessions</th><th scope="col">Talla que s’emporten</th></tr></thead>
              <tbody>{dubte.per_model.map((m) => (
                <tr key={m.model}>
                  <td><Link className="nom-model" to={`/peces/${encodeURIComponent(m.model)}`}>{m.nom}</Link></td>
                  <td className="n">{enter(m.sessions_dubte)} <Petita si={m.mostra_petita} /></td>
                  <td className="n">{pct(m.pct_sessions_model)}</td>
                  <td>{m.talla_mes_comprada ?? '—'}</td>
                </tr>
              ))}</tbody>
            </table></div>
          </div>
          <div className="panell" style={{ padding: 0 }}>
            <h3 style={{ padding: '14px 14px 0' }}>Quina talla guanya</h3>
            <div style={{ padding: '6px 14px 0' }}>{llegendaCompra()}</div>
            {dubte.parells_talla.length ? <ParellsTalla parells={dubte.parells_talla} /> : <Buit titol="Cap dubte de talla">Ningú s’ha emportat la mateixa peça en dues talles.</Buit>}
          </div>
        </div>
      </Seccio>

      <div className="reixa-2">
        <Seccio titol="Segons el temps a la cabina" subtitol="Les sessions molt curtes gairebé mai acaben en compra: sovint la peça no ha entrat bé.">
          <div className="panell">
            <Columnes titol="Sessions amb compra segons la durada" nomEixX="Durada" x={d.per_durada.map((x) => x.tram)} unitat="pct"
              series={[{ nom: 'Sessions amb compra', valors: d.per_durada.map((x) => x.conversio_sessio) }]}
              subetiquetes={d.per_durada.map((x) => `${enter(x.sessions)} sessions`)} alcada={200} />
          </div>
        </Seccio>
        <Seccio titol="Segons l’hora" subtitol="Quantes sessions hi ha a cada hora del dia. Útil per saber quan cal més gent a la sala.">
          <div className="panell">
            <Columnes titol="Sessions per hora" nomEixX="Hora" x={d.per_hora.map((x) => `${x.hora} h`)}
              series={[{ nom: 'Sessions', valors: d.per_hora.map((x) => x.sessions) }]}
              subetiquetes={d.per_hora.map((x) => pct(x.conversio_sessio))} alcada={200} />
            <p className="petit muted" style={{ margin: '6px 0 0' }}>A sota de cada hora, el % de sessions amb compra.</p>
          </div>
        </Seccio>
      </div>
    </>
  );
}
