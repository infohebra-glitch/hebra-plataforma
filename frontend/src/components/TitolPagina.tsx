import { useEffect, useId, type ReactNode } from 'react';
import { useFiltre } from '../context/Filtre';
import { rang } from '../lib/format';

/** Títol de pàgina amb el període actiu; també posa el <title> del document. */
export function TitolPagina({ titol, children, accions, senseperiode }: { titol: string; children?: ReactNode; accions?: ReactNode; senseperiode?: boolean }) {
  const { periode } = useFiltre();
  useEffect(() => { document.title = `${titol} · Hebra`; }, [titol]);
  return (
    <div className="titol-pagina">
      <div>
        <h1 id="titol-pagina" tabIndex={-1}>{titol}</h1>
        {children && <p>{children}</p>}
        {!senseperiode && <p className="petit">Període: {rang(periode.des, periode.fins)} · només proves de confiança alta i mitjana</p>}
      </div>
      {accions && <div className="accions">{accions}</div>}
    </div>
  );
}

export function Seccio({ titol, subtitol, children }: { titol: string; subtitol?: ReactNode; children: ReactNode }) {
  const id = useId();
  return (
    <section className="seccio" aria-labelledby={id}>
      <h2 id={id}>{titol}</h2>
      {subtitol && <p className="subtitol">{subtitol}</p>}
      {children}
    </section>
  );
}
