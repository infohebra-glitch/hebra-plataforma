/** Targeta d'una prova A/B: grups, diferència amb interval, p-valor en paraules, mostra i conclusió. */
import type { Experiment } from '../api/types';
import { deCada, diaCurt, enter, pct, pValorEnParaules, punts } from '../lib/format';
import { IntervalConfianca } from './grafics/IntervalConfianca';
import { Mesurador } from './grafics/Mesurador';
import { MostraPetita } from './Insignies';

const VARIABLES: Record<string, string> = { origen: 'l’origen a la fitxa', peticio_talla: 'la petició de talla a la fitxa', preu: 'el preu', exposicio: 'l’exposició' };

export function nomGrup(variable: string, g: string): string {
  if (variable === 'origen') return g === 'amb' ? 'Amb origen visible' : g === 'sense' ? 'Sense origen (control)' : g;
  if (g === 'amb') return `Amb ${VARIABLES[variable] ?? variable}`;
  if (g === 'sense') return 'Sense canvi (control)';
  return g;
}

const ESTATS: Record<string, [string, string]> = {
  actiu: ['En curs', 'insignia-neutra'], acabat: ['Acabada', 'insignia-bo'], planificat: ['Planificada', 'insignia-mostra'],
};

export function TargetaExperiment({ e, compacta = false }: { e: Experiment; compacta?: boolean }) {
  const grups = Object.entries(e.grups);
  const total = grups.reduce((s, [, g]) => s + g.proves, 0);
  const [estatNom, estatClasse] = ESTATS[e.estat] ?? [e.estat, 'insignia-mostra'];
  const necessaries = e.proves_necessaries;
  return (
    <article className="panell experiment" aria-labelledby={`exp-${e.id}`}>
      <div className="targeta-cap">
        <h3 id={`exp-${e.id}`}>{compacta ? 'Efecte de l’origen en aquest model' : e.hipotesi}</h3>
        <span className={`insignia ${estatClasse}`}>{estatNom}</span>
      </div>
      <ul className="metadades">
        <li><b>Variable:</b> {VARIABLES[e.variable] ?? e.variable}</li>
        <li><b>Sorteig:</b> per {e.unitat === 'dia' ? 'dies' : e.unitat}</li>
        <li><b>Del</b> {diaCurt(e.inici)} <b>al</b> {diaCurt(e.fi)}</li>
        {e.estat === 'actiu' && e.setmanes_restants != null && <li><b>Queden:</b> {e.setmanes_restants} {e.setmanes_restants === 1 ? 'setmana' : 'setmanes'}</li>}
      </ul>

      <div className="grups">
        {grups.map(([g, v], i) => (
          <div key={g} className="grup">
            <span className="grup-titol"><span className={`clau-quadre ${i === 0 ? 'bg-s1' : 'bg-neutra'}`} aria-hidden="true" />{nomGrup(e.variable, g)}</span>
            <span className="valor-grup">{pct(v.conversio)}</span>
            <span className="petit muted">{deCada(v.compres, v.proves)} proves acaben en compra</span>
            <MostraPetita n={v.proves} minim={e.proves_minimes} />
          </div>
        ))}
      </div>

      {e.diferencia !== null && e.ic95 ? (
        <div>
          <p style={{ marginBottom: 2 }}><b>Diferència: {punts(e.diferencia, 1)}</b> <span className="muted">(interval del 95 %: de {punts(e.ic95[0], 1)} a {punts(e.ic95[1], 1)})</span></p>
          <IntervalConfianca diferencia={e.diferencia} ic95={e.ic95} esquerra={nomGrup(e.variable, 'sense').replace(' (control)', '') + ' ven més'} dreta={nomGrup(e.variable, 'amb') + ' ven més'} />
          <p className="petit">{pValorEnParaules(e.p_valor)}{' '}
            {e.ic95[0] < 0 && e.ic95[1] > 0 ? 'L’interval inclou el zero: amb les dades d’ara, la diferència real podria ser nul·la o fins i tot de signe contrari.' : 'L’interval no inclou el zero.'}</p>
        </div>
      ) : <p className="muted">Encara no hi ha prou dades per calcular la diferència.</p>}

      <div>
        <div className="fila entre petit" style={{ marginBottom: 4 }}>
          <span><b>Mostra:</b> {enter(total)} proves{necessaries ? ` de les ${enter(necessaries)} necessàries` : ''}</span>
          {necessaries ? <span className="muted">{pct(Math.min(1, total / necessaries))}</span> : null}
        </div>
        {necessaries ? <Mesurador valor={total} total={necessaries} etiqueta="Proves recollides respecte de les necessàries" /> : null}
        <p className="petit muted" style={{ marginTop: 4 }}>
          {necessaries ? `Proves necessàries per detectar amb un 80 % de seguretat una diferència com l’observada. ` : ''}
          Mínim de {e.proves_minimes} proves per grup per mirar-ne el resultat{e.mostra_suficient ? ' (assolit).' : ' (encara no assolit).'}
        </p>
      </div>

      <p className="conclusio">{e.conclusio}</p>
    </article>
  );
}
