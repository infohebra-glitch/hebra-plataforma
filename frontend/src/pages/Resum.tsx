import { Link } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { Accio, Resum as TResum } from '../api/types';
import { Consulta, Esquelet } from '../components/Estat';
import { MostraPetita } from '../components/Insignies';
import { Rajola, type Delta } from '../components/Rajola';
import { SerieTemporal } from '../components/grafics/SerieTemporal';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { deCada, diaCurt, diaLlarg, diaSetmana, enter, pct, punts, segons } from '../lib/format';
import { insight } from '../lib/etiquetes';
import { useApi } from '../lib/useApi';

function deltaConversio(k: TResum['kpi']): Delta | null {
  if (k.variacio_conversio === null) return null;
  const v = Math.round(k.variacio_conversio * 100);
  return {
    text: `${punts(k.variacio_conversio)} vs període anterior`,
    sentit: v > 0 ? 'bo' : v < 0 ? 'dolent' : 'neutre',
    descripcio: `(abans era ${pct(k.conversio_periode_anterior)})`,
  };
}

export function TargetaAccio({ accio }: { accio: Accio | null }) {
  return (
    <section className="panell accio-setmana" aria-labelledby="titol-accio">
      <span className="etiqueta-seccio" id="titol-accio">Acció de la setmana</span>
      {accio ? (
        <>
          <p className="text">{accio.text}</p>
          <ul className="metadades">
            {accio.responsable && <li><b>Qui:</b> {accio.responsable}</li>}
            {accio.data_limit && <li><b>Abans del</b> {diaCurt(accio.data_limit)}</li>}
            {accio.insight && <li><b>Per:</b> {insight(accio.insight)}</li>}
            {accio.model && <li><Link to={`/peces/${encodeURIComponent(accio.model)}`}>Veure la peça</Link></li>}
          </ul>
        </>
      ) : <p className="text muted">Cap acció clara en aquest període: cap model queda molt per sota de la seva categoria i no hi ha demanda perduda destacable.</p>}
    </section>
  );
}

function Xifres({ r }: { r: TResum }) {
  const k = r.kpi;
  return (
    <div className="rajoles tres">
      <Rajola etiqueta="Proves" valor={enter(k.proves)} nota={<>en {enter(k.sessions)} sessions de cabina · {enter(k.proves_ambigues)} ambigües no comptades</>} />
      <Rajola etiqueta="Conversió de provador" valor={pct(k.conversio)} delta={deltaConversio(k)} nota={<>{deCada(k.compres_atribuides, k.proves)} proves acaben en compra</>} insignia={<MostraPetita n={k.proves} />} />
      <Rajola etiqueta="Venut sense provar" valor={enter(k.venut_sense_provar)} nota={<>{pct(k.venut_sense_provar_pct, 1)} de {enter(k.unitats_venudes)} unitats venudes</>} />
      <Rajola etiqueta="Temps de resposta" valor={segons(k.temps_resposta_mediana_s)} nota={k.temps_resposta_mediana_s === null ? 'Sense peticions de talla amb resposta' : <>mediana · {pct(k.pct_resposta_sota_90s)} per sota de 90 s · {enter(k.peticions_talla)} peticions</>} />
      <Rajola etiqueta="Demanda perduda" valor={enter(k.demanda_perduda)} destacada={k.demanda_perduda > 0} nota={<>peticions de talles que no hi eren · <Link to="/per-que">detall</Link></>} />
      <Rajola etiqueta="Peces abandonades" valor={enter(k.peces_abandonades)} nota="més de 30 min fora de la sala sense vendre’s" />
    </div>
  );
}

export function Resum() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.resum(filtre, s), [clau]);
  return (
    <>
      <TitolPagina titol="Resum">Què s’ha provat, què s’ha venut i què cal fer aquesta setmana.</TitolPagina>
      <Consulta q={q} esquelet={<><Esquelet tipus="rajoles" /><div style={{ height: 16 }} /><Esquelet tipus="grafic" /></>}>
        {(r) => (
          <>
            <Xifres r={r} />
            <div className="reixa-2" style={{ marginTop: 16 }}>
              <TargetaAccio accio={r.accio} />
              <section className="panell" aria-labelledby="titol-alertes">
                <h3 id="titol-alertes">Alertes obertes</h3>
                <p className="rajola-valor" style={{ margin: '6px 0' }}>{enter(r.alertes_obertes)}</p>
                <p className="muted petit">{r.alertes_obertes ? 'Peticions de talla pendents, peces abandonades i models a revisar.' : 'Tot al dia: cap alerta pendent.'}</p>
                <Link className="boto" to="/dependent">Obre la web del dependent</Link>
              </section>
            </div>
            <Seccio titol="Proves i compres per dia" subtitol="Les franges de color marquen els dies en què la fitxa NFC ensenyava l’origen de la peça (prova A/B per dies).">
              <div className="panell">
                {r.serie_diaria.length ? (
                  <SerieTemporal
                    titol="Proves i compres per dia"
                    x={r.serie_diaria.map((d) => d.data)}
                    etiquetaX={(i) => (r.serie_diaria.length > 10 ? diaCurt(r.serie_diaria[i].data) : diaSetmana(r.serie_diaria[i].data))}
                    detallX={(i) => diaLlarg(r.serie_diaria[i].data)}
                    series={[
                      { clau: 'proves', nom: 'Proves', classe: 's1', valors: r.serie_diaria.map((d) => d.proves) },
                      { clau: 'compres', nom: 'Compres després de provar', classe: 's2', valors: r.serie_diaria.map((d) => d.compres) },
                    ]}
                    formatY={enter}
                    formatValor={(v, s, i) => (v === null ? '—' : s.clau === 'compres' ? `${enter(v)} (${pct(r.serie_diaria[i].conversio)})` : enter(v))}
                    bandes={r.serie_diaria.map((d) => d.grup_origen === 'amb')}
                    nomBanda="Dia amb origen visible"
                  />
                ) : <p className="muted">Encara no hi ha dies amb dades en aquest període.</p>}
              </div>
            </Seccio>
          </>
        )}
      </Consulta>
    </>
  );
}
