import { analitica } from '../api/endpoints';
import type { EstatPeticio } from '../api/types';
import { Consulta, Esquelet } from '../components/Estat';
import { Rajola } from '../components/Rajola';
import { MapaCalor } from '../components/grafics/MapaCalor';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { ESTATS_PETICIO } from '../lib/etiquetes';
import { DIES_SETMANA, DIES_SETMANA_LLARG, decimal, enter, pct, segons } from '../lib/format';
import { useApi } from '../lib/useApi';

export function Servei() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.servei(filtre, s), [clau]);
  return (
    <>
      <TitolPagina titol="Servei a la cabina">Peticions de talla des de la fitxa, quant triguem a portar-les i quan s’omplen les cabines.</TitolPagina>
      <Consulta q={q} esquelet={<><Esquelet tipus="rajoles" /><div style={{ height: 16 }} /><Esquelet tipus="taula" /></>}>
        {(s) => {
          const total = Object.values(s.per_estat).reduce((a, b) => a + b, 0);
          const dies = [...new Set(s.ocupacio.mapa.map((c) => c.dia_setmana))].sort();
          const hores = [...new Set(s.ocupacio.mapa.map((c) => c.hora))].sort((a, b) => a - b);
          const sessionsTotal = s.peces_per_sessio.reduce((a, b) => a + b.sessions, 0);
          return (
            <>
              <div className="rajoles">
                <Rajola etiqueta="Peticions de talla" valor={enter(s.peticions)} nota={<>{decimal(s.peticions_per_sessio === null ? null : s.peticions_per_sessio * 100)} per cada 100 sessions</>} />
                <Rajola etiqueta="Temps de resposta" valor={segons(s.mediana_s)} nota="mediana entre «demanat» i «lliurat»" />
                <Rajola etiqueta="Per sota de 90 s" valor={pct(s.pct_sota_90s)} nota={<>de les peticions lliurades</>} />
                <Rajola etiqueta="Durada d’una sessió" valor={segons(s.ocupacio.durada_mitjana_s)} nota="mitjana a la cabina" />
                <Rajola etiqueta="Totes les cabines plenes" valor={pct(s.ocupacio.pct_temps_totes_plenes)} nota="del temps obert" />
              </div>
              <div className="reixa-2">
                <Seccio titol="Com han acabat les peticions" subtitol={`${enter(total)} peticions en total.`}>
                  <div className="panell" style={{ padding: 0 }}>
                    <table>
                      <caption className="sr-only">Peticions per estat</caption>
                      <thead><tr><th scope="col">Estat</th><th scope="col" className="n">Peticions</th><th scope="col" className="n">%</th></tr></thead>
                      <tbody>
                        {(Object.keys(ESTATS_PETICIO) as EstatPeticio[]).map((e) => (
                          <tr key={e}><td>{ESTATS_PETICIO[e]}</td><td className="n">{enter(s.per_estat[e] ?? 0)}</td><td className="n">{pct(total ? (s.per_estat[e] ?? 0) / total : null)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Seccio>
                <Seccio titol="Peces per sessió" subtitol={`Quantes peces s’emporten a la cabina i quantes sessions acaben amb compra (${enter(sessionsTotal)} sessions).`}>
                  <div className="panell" style={{ padding: 0 }}>
                    <table>
                      <caption className="sr-only">Peces per sessió</caption>
                      <thead><tr><th scope="col">Peces</th><th scope="col" className="n">Sessions</th><th scope="col" className="n">Amb compra</th></tr></thead>
                      <tbody>
                        {s.peces_per_sessio.map((p, i) => (
                          <tr key={p.peces}><td>{i === s.peces_per_sessio.length - 1 && p.peces >= 5 ? `${p.peces} o més` : p.peces}</td><td className="n">{enter(p.sessions)}</td><td className="n">{pct(p.pct_amb_compra)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Seccio>
              </div>
              <Seccio titol="Ocupació per dia i hora" subtitol="Sessions de cabina a cada franja. Com més fosc, més sessions; el globus diu quina part del temps totes les cabines eren plenes.">
                <div className="panell">
                  <MapaCalor
                    titol="Sessions per dia de la setmana i hora"
                    capFila="Dia"
                    files={dies.map((d) => ({ clau: String(d), nom: <span title={DIES_SETMANA_LLARG[d]}>{DIES_SETMANA[d]}</span> }))}
                    columnes={hores.map((h) => ({ clau: String(h), nom: `${h} h` }))}
                    llegendaEscala={['menys sessions', 'més']}
                    cel={(d, h) => {
                      const c = s.ocupacio.mapa.find((x) => x.dia_setmana === Number(d) && x.hora === Number(h));
                      return c ? { v: c.sessions, text: enter(c.sessions), titol: `${DIES_SETMANA_LLARG[c.dia_setmana]} a les ${c.hora} h: ${c.sessions} sessions; totes plenes el ${pct(c.pct_totes_plenes)} del temps` } : { v: null, text: '·' };
                    }}
                  />
                </div>
              </Seccio>
            </>
          );
        }}
      </Consulta>
    </>
  );
}
