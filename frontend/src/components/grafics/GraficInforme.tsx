/** Dibuixa un gràfic d'informe (E.2) amb els components propis, segons el tipus. */
import type { GraficInforme as TGrafic } from '../../api/types';
import { formatUnitat } from '../../lib/escala';
import { Barres } from './Barres';
import { Columnes } from './Columnes';
import { Dispersio } from './Dispersio';
import { Donut } from './Donut';
import { SerieTemporal } from './SerieTemporal';

export function GraficInforme({ g }: { g: TGrafic }) {
  let cos;
  if (g.tipus === 'dispersio') {
    cos = <Dispersio titol={g.titol} nomX={g.series[0]?.nom ?? ''} nomY="Acaben en compra" alcada={300}
      punts={g.eix_x.map((nom, i) => ({ clau: `${i}-${nom}`, nom, x: g.series[0]?.valors[i] ?? 0, y: g.series[1]?.valors[i] ?? null, alerta: !!g.destaca?.[i] }))} />;
  } else if (g.tipus === 'donut') cos = <Donut titol={g.titol} etiquetes={g.eix_x} valors={g.series[0]?.valors ?? []} unitat={g.unitat} />;
  else if (g.tipus === 'linia') {
    cos = (
      <SerieTemporal titol={g.titol} x={g.eix_x} etiquetaX={(i) => g.eix_x[i]} alcada={200}
        series={g.series.slice(0, 3).map((s, k) => ({ clau: s.nom, nom: s.nom, classe: (['s1', 's2', 's3'] as const)[k], valors: s.valors }))}
        formatY={(n) => formatUnitat(n, g.unitat)} />
    );
  } else if (g.tipus === 'barres' && g.series.length === 1 && g.eix_x.some((e) => String(e).length > 9)) {
    // Una sola sèrie amb noms llargs (models, categories): barres horitzontals amb el valor escrit,
    // que es llegeixen d'un cop d'ull sense haver de tombar el cap per llegir l'eix.
    const vals = g.series[0].valors;
    cos = <Barres titol={g.titol} fmt={(n) => formatUnitat(n, g.unitat)} max={g.unitat === 'pct' ? Math.max(0.01, ...vals.map((v) => v ?? 0)) : undefined}
      items={g.eix_x.map((e, i) => ({ clau: `${i}-${e}`, etiqueta: String(e), n: vals[i] ?? 0 }))} />;
  } else cos = <Columnes titol={g.titol} x={g.eix_x} series={g.series} unitat={g.unitat} apilades={g.tipus === 'barres_apilades'} alcada={200} />;
  return (
    <figure className="grafic-informe" aria-labelledby={`g-${g.id}`}>
      <figcaption id={`g-${g.id}`} className="grafic-titol">{g.titol}</figcaption>
      {g.lectura && <p className="grafic-lectura">{g.lectura}</p>}
      {cos}
      {g.nota && <p className="petit muted" style={{ margin: '6px 0 0' }}>{g.nota}</p>}
    </figure>
  );
}
