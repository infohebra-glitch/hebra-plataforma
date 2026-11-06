/** Dibuixa un gràfic d'informe (E.2) amb els components propis, segons el tipus. */
import type { GraficInforme as TGrafic } from '../../api/types';
import { formatUnitat } from '../../lib/escala';
import { Columnes } from './Columnes';
import { Donut } from './Donut';
import { SerieTemporal } from './SerieTemporal';

export function GraficInforme({ g }: { g: TGrafic }) {
  let cos;
  if (g.tipus === 'donut') cos = <Donut titol={g.titol} etiquetes={g.eix_x} valors={g.series[0]?.valors ?? []} unitat={g.unitat} />;
  else if (g.tipus === 'linia') {
    cos = (
      <SerieTemporal titol={g.titol} x={g.eix_x} etiquetaX={(i) => g.eix_x[i]} alcada={200}
        series={g.series.slice(0, 3).map((s, k) => ({ clau: s.nom, nom: s.nom, classe: (['s1', 's2', 's3'] as const)[k], valors: s.valors }))}
        formatY={(n) => formatUnitat(n, g.unitat)} />
    );
  } else cos = <Columnes titol={g.titol} x={g.eix_x} series={g.series} unitat={g.unitat} apilades={g.tipus === 'barres_apilades'} alcada={200} />;
  return (
    <figure className="grafic-informe" aria-labelledby={`g-${g.id}`}>
      <figcaption id={`g-${g.id}`} className="grafic-titol">{g.titol}</figcaption>
      {cos}
      {g.nota && <p className="petit muted" style={{ margin: '6px 0 0' }}>{g.nota}</p>}
    </figure>
  );
}
