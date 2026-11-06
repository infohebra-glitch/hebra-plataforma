/** Rajola de xifra (stat tile): etiqueta, valor, variació opcional i nota amb el denominador. */
import type { ReactNode } from 'react';

export interface Delta { text: string; sentit: 'bo' | 'dolent' | 'neutre'; descripcio: string }

export function Rajola({ etiqueta, valor, delta, nota, destacada, insignia }: {
  etiqueta: string; valor: ReactNode; delta?: Delta | null; nota?: ReactNode; destacada?: boolean; insignia?: ReactNode;
}) {
  const fletxa = delta?.sentit === 'bo' ? '▲' : delta?.sentit === 'dolent' ? '▼' : '';
  return (
    <div className={`rajola${destacada ? ' destacada' : ''}`}>
      <span className="rajola-etiqueta">{etiqueta}</span>
      <span className="rajola-valor">{valor}</span>
      {delta && (
        <span className={`rajola-delta ${delta.sentit}`}>
          {fletxa && <span aria-hidden="true">{fletxa}</span>}
          {delta.text}
          <span className="sr-only"> {delta.descripcio}</span>
        </span>
      )}
      {nota && <span className="rajola-nota">{nota}</span>}
      {insignia}
    </div>
  );
}
