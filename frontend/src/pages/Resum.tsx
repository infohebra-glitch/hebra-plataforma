import { Link } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { Accio, EstatCopia as TEstatCopia, EstatSistema as TEstatSistema, Resum as TResum } from '../api/types';
import { Consulta, Esquelet } from '../components/Estat';
import { MostraPetita } from '../components/Insignies';
import { Panorama } from '../components/Panorama';
import { TargetaLotProva, useLotProva } from '../components/LotProva';
import { Rajola, type Delta } from '../components/Rajola';
import { ProvesCompresDia } from '../components/ProvesCompresDia';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { deCada, diaCurt, enter, hora, pct, punts, segons } from '../lib/format';
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

const quan = (iso: string | null) => (iso ? `${diaCurt(iso)}${iso.length > 10 ? `, ${hora(iso)}` : ''}` : 'mai');

function CopiaSeguretat({ c }: { c: TEstatCopia }) {
  return (
    <p className="petit" style={{ marginTop: 6 }}>
      <b>Còpia de seguretat:</b> {quan(c.darrera)}
      {c.darrera && (c.remot ? ' (guardada fora del servidor)' : ' (només al servidor)')}
      {c.alerta && (
        <span className="insignia insignia-critic" style={{ marginLeft: 6 }}>
          {c.error_remot ? 'no s’ha pogut enviar fora' : c.darrera ? `fa més de ${c.hores_alerta} h` : 'cap còpia'}
        </span>
      )}
    </p>
  );
}

/** Pantalla «Estat del sistema» del manual: si cada cabina envia dades i si arriben les vendes. */
function EstatDelSistema({ e }: { e: TEstatSistema }) {
  const alertes = e.cabines.filter((c) => c.alerta).length;
  return (
    <Seccio titol="Estat del sistema" subtitol={`Una cabina surt en vermell si fa més de ${e.hores_alerta} h que no envia dades (després d’un dia de tancament és normal fins a la primera prova).`}>
      <div className="panell">
        <div className="taula-wrap"><table>
          <caption className="sr-only">Darrera dada de cada cabina</caption>
          <thead><tr><th scope="col">Cabina</th><th scope="col">Darrera lectura</th><th scope="col">Darrer sensor</th><th scope="col">Estat</th></tr></thead>
          <tbody>
            {e.cabines.map((c) => (
              <tr key={c.cabina_id}>
                <th scope="row">{c.nom} <span className="muted petit">{c.botiga_id}</span></th>
                <td>{quan(c.darrera_lectura)}</td>
                <td>{quan(c.darrer_sensor)}</td>
                <td>{c.alerta ? <span className="insignia insignia-critic">Sense dades</span> : <span className="insignia insignia-bo">Envia dades</span>}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
        <p className="petit" style={{ marginTop: 10 }}>
          <b>Darrera venda importada:</b> {quan(e.darrera_venda)}
          {e.dies_sense_vendes !== null && e.dies_sense_vendes > 7 && <span className="insignia insignia-critic" style={{ marginLeft: 6 }}>fa {e.dies_sense_vendes} dies</span>}
          {' · '}<b>Peces desconegudes:</b> {pct(e.pct_desconegudes, 1)} ({enter(e.peces_desconegudes)} de {enter(e.peces_llegides)} etiquetes llegides al període no són a la taula d’etiquetes)
          {(e.dies_sense_vendes ?? 99) > 7 && <> · <Link to="/dades">Importa les vendes</Link></>}
          {alertes > 0 && <> · {alertes === 1 ? 'Una cabina' : `${alertes} cabines`} sense dades: mira la xarxa, el lector i la passarel·la (manual, capítol 19).</>}
        </p>
        {e.copia_seguretat && <CopiaSeguretat c={e.copia_seguretat} />}
      </div>
    </Seccio>
  );
}

/** Quan encara no hi ha cap dada: què cal per començar i, per a la marca, el lot de prova. */
function Benvinguda() {
  const { lot } = useLotProva();
  return (
    <div className="benvinguda-buida">
      <div>
        <p className="kicker">Benvinguda</p>
        <h2>Encara no hi ha dades en aquest període</h2>
        <p>El tauler s’omple sol quan les cabines comencen a llegir les etiquetes i arriben les vendes. Per arrencar:</p>
      </div>
      <ol>
        <li>Connecta la botiga en línia o el TPV a <Link to="/dades">Connexions i dades</Link> (o puja un CSV).</li>
        <li>Revisa la <Link to="/fitxa">fitxa NFC</Link> que veurà el client quan toqui la peça.</li>
        <li>Engega les cabines: cada prova apareixerà aquí i a <Link to="/provadors">Provadors en directe</Link>.</li>
      </ol>
      {lot && !lot.carregat && <TargetaLotProva compacta />}
    </div>
  );
}

export function Resum() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.resum(filtre, s), [clau]);
  const qs = useApi((s) => analitica.estatSistema(filtre, s), [clau]);
  const qp = useApi((s) => analitica.panorama(filtre, s), [clau]);
  return (
    <>
      <TitolPagina titol="Resum">Què s’ha provat, què s’ha venut i què cal fer aquesta setmana.</TitolPagina>
      <Consulta q={q} esquelet={<><Esquelet tipus="rajoles" /><div style={{ height: 16 }} /><Esquelet tipus="grafic" /></>}>
        {(r) => r.kpi.sessions === 0 && r.serie_diaria.every((d) => !d.proves) ? <Benvinguda /> : (
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
            <Seccio titol="Proves i compres per dia" subtitol="Compara-ho amb un altre període o col·lecció, o mira només una franja del dia o els dies de pluja. Sense filtres, les franges de color marquen els dies en què la fitxa ensenyava l’origen.">
              <ProvesCompresDia r={r} />
            </Seccio>
            {qp.dades && <Panorama p={qp.dades} />}
          </>
        )}
      </Consulta>
      {qs.dades && <EstatDelSistema e={qs.dades} />}
    </>
  );
}
