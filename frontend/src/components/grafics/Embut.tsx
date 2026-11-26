/**
 * Embut (v0.5): de la peça tocada a la peça venuda, com als taulers de provador del sector.
 * Cada graó porta el seu número i el pas respecte del graó anterior; el color no és mai l'única pista.
 */
import { enter, pct } from '../../lib/format';

export interface GraoEmbut { clau: string; nom: string; n: number; nota?: string }

export function Embut({ titol, graons }: { titol: string; graons: GraoEmbut[] }) {
  const max = Math.max(1, ...graons.map((g) => g.n));
  return (
    <ol className="embut" aria-label={titol}>
      {graons.map((g, i) => {
        const ant = i > 0 ? graons[i - 1].n : null;
        return (
          <li key={g.clau} className={`embut-${i}`}>
            <div className="embut-cap">
              <span className="nom">{g.nom}</span>
              <span className="n">{enter(g.n)}</span>
            </div>
            <span className="pista" aria-hidden="true"><span className="ple" style={{ width: `${Math.max(2, (g.n / max) * 100)}%` }} /></span>
            <span className="pas">{g.nota ?? (ant ? `${pct(g.n / ant)} del pas anterior` : 'punt de partida')}</span>
          </li>
        );
      })}
    </ol>
  );
}
