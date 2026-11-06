import { Link } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { Rajola } from '../components/Rajola';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { decimal, enter, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

export function Estoc() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.estoc(filtre, s), [clau]);
  return (
    <>
      <TitolPagina titol="Estoc">Peces que no es mouen i peces que acabaran a les rebaixes si no hi fem res.</TitolPagina>
      <Consulta q={q} esquelet={<Esquelet tipus="taula" />}>
        {(e) => (
          <>
            <div className="rajoles">
              <Rajola etiqueta="Unitats parades" valor={enter(e.parat.reduce((s, x) => s + x.unitats, 0))} nota={<>en {enter(e.parat.length)} referències sense cap prova ni venda en 21 dies</>} />
              <Rajola etiqueta="Models en risc de rebaixa" valor={enter(e.risc_rebaixa.length)} nota="molta cobertura i poca conversió" />
              <Rajola etiqueta="Precisió de l’estoc" valor={e.precisio ? pct(e.precisio.error_mitja_pct, 1) : '—'} nota={e.precisio ? <>error mitjà entre recompte manual i RFID · {enter(e.precisio.recomptes)} recomptes</> : 'Encara cap recompte manual'} />
            </div>
            <Seccio titol="Estoc parat" subtitol="Unitats amb 0 proves i 0 vendes en els darrers 21 dies. Abans de rebaixar-les, pensa a traspassar-les a una altra botiga o al web.">
              {e.parat.length ? (
                <div className="panell" style={{ padding: 0 }}><div className="taula-wrap"><table>
                  <caption className="sr-only">Estoc parat</caption>
                  <thead><tr><th scope="col">Model</th><th scope="col">Talla</th><th scope="col" className="n">Unitats</th><th scope="col" className="n">Dies sense activitat</th><th scope="col">GTIN</th></tr></thead>
                  <tbody>{e.parat.map((p) => (
                    <tr key={p.gtin}><td><Link className="nom-model" to={`/peces/${encodeURIComponent(p.model)}`}>{p.nom}</Link></td><td>{p.talla}</td><td className="n">{enter(p.unitats)}</td><td className="n">{enter(p.dies_sense_activitat)}</td><td className="codi">{p.gtin}</td></tr>
                  ))}</tbody>
                </table></div></div>
              ) : <div className="panell"><Buit titol="Res parat">Totes les unitats en estoc s’han provat o venut en els darrers 21 dies.</Buit></div>}
            </Seccio>
            <Seccio titol="Risc de rebaixa" subtitol="Models amb estoc per a més de 8 setmanes al ritme de venda actual i conversió al quartil inferior de la seva categoria.">
              {e.risc_rebaixa.length ? (
                <div className="panell" style={{ padding: 0 }}><div className="taula-wrap"><table>
                  <caption className="sr-only">Risc de rebaixa</caption>
                  <thead><tr><th scope="col">Model</th><th scope="col" className="n">Unitats</th><th scope="col" className="n">Cobertura</th><th scope="col" className="n">Conversió</th></tr></thead>
                  <tbody>{e.risc_rebaixa.map((r) => (
                    <tr key={r.model}><td><Link className="nom-model" to={`/peces/${encodeURIComponent(r.model)}`}>{r.nom}</Link></td><td className="n">{enter(r.unitats)}</td><td className="n">{r.cobertura_setmanes === null ? '—' : `${decimal(r.cobertura_setmanes)} setm.`}</td><td className="n">{pct(r.conversio)}</td></tr>
                  ))}</tbody>
                </table></div></div>
              ) : <div className="panell"><Buit titol="Cap model en risc">Cap model combina molta cobertura amb poca conversió.</Buit></div>}
            </Seccio>
          </>
        )}
      </Consulta>
    </>
  );
}
