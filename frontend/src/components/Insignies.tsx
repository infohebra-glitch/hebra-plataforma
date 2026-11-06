import { MOSTRA_MINIMA } from '../lib/etiquetes';
import { enter } from '../lib/format';

/** «Mostra petita» quan un grup té menys de 30 proves: el percentatge pot enganyar. */
export function MostraPetita({ n, minim = MOSTRA_MINIMA }: { n: number; minim?: number }) {
  if (n >= minim) return null;
  return (
    <span className="insignia insignia-mostra" title={`Només ${enter(n)} proves: amb menys de ${minim}, el percentatge pot canviar molt amb poques compres.`}>
      Mostra petita<span className="sr-only">: només {enter(n)} proves, menys de {minim}</span>
    </span>
  );
}

export function MoltProvat() {
  return <span className="insignia insignia-alerta"><span aria-hidden="true">●</span> Molt provat, poc venut</span>;
}

export function Estimacio({ text = 'Estimació' }: { text?: string }) {
  return <span className="insignia insignia-estimacio">{text}</span>;
}
