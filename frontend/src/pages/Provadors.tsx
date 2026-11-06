/** Provadors en directe (B.2): una targeta per cabina que s'actualitza sola pel flux. */
import { useEffect, useRef, useState } from 'react';
import { Buit, ErrorEstat, Esquelet } from '../components/Estat';
import { TargetaCabina, useAra } from '../components/Cabines';
import { Rajola } from '../components/Rajola';
import { TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { enter, hora } from '../lib/format';
import { useCabines } from '../lib/useCabines';

export function Provadors() {
  const { filtre } = useFiltre();
  const { botigues } = useSessio();
  const { dades, error, recarrega, estatFlux, darrerCanvi } = useCabines(filtre.botiga);
  const ara = useAra(5000);
  const [canviades, setCanviades] = useState<Set<string>>(new Set());
  const temps = useRef<number>();
  useEffect(() => {
    if (!darrerCanvi) return;
    setCanviades((s) => new Set(s).add(darrerCanvi.id));
    window.clearTimeout(temps.current);
    temps.current = window.setTimeout(() => setCanviades(new Set()), 3000);
  }, [darrerCanvi]);

  const perBotiga = botigues.map((b) => ({ b, cabines: dades?.cabines.filter((c) => c.botiga_id === b.id) ?? [] })).filter((x) => !filtre.botiga || x.b.id === filtre.botiga);
  const nomFlux = { connectant: 'Connectant…', connectat: 'En directe', reconnectant: 'Reconnectant…' }[estatFlux];

  return (
    <>
      <TitolPagina titol="Provadors en directe" senseperiode accions={<span className={`estat-connexio ${estatFlux}`}>{nomFlux}{dades ? ` · actualitzat a les ${hora(dades.generat)}` : ''}</span>}>
        Què passa ara mateix a cada cabina: si està ocupada, quines peces hi ha dins i si algú espera una talla. S’actualitza sol.
      </TitolPagina>
      <p className="sr-only" aria-live="polite">{darrerCanvi?.text ?? ''}</p>
      {error && !dades && <ErrorEstat error={error} reintenta={recarrega} />}
      {!dades && !error && <Esquelet tipus="rajoles" />}
      {dades && (
        <>
          <div className="rajoles">
            <Rajola etiqueta="Ocupades ara" valor={`${enter(dades.resum.ocupades)} de ${enter(dades.cabines.length)}`} nota="cabines amb algú dins" />
            <Rajola etiqueta="Lliures" valor={enter(dades.resum.lliures)} nota="a punt per entrar-hi" />
            <Rajola etiqueta="Sessions avui" valor={enter(dades.resum.sessions_avui)} nota="vegades que algú ha entrat a provar" />
            <Rajola etiqueta="Proves avui" valor={enter(dades.resum.proves_avui)} nota="peces provades, de confiança alta i mitjana" />
          </div>
          {perBotiga.map(({ b, cabines }) => (
            <section key={b.id} className="seccio" aria-labelledby={`cab-${b.id}`}>
              <h2 id={`cab-${b.id}`}>{b.nom}</h2>
              {cabines.length ? (
                <ul className="llista-targetes reixa-cabines">
                  {cabines.map((c) => <TargetaCabina key={c.cabina_id} c={c} nova={canviades.has(c.cabina_id)} ara={ara} />)}
                </ul>
              ) : <div className="panell"><Buit titol="Sense lectors a les cabines">Aquesta botiga té el nivell bàsic (sense antenes a les cabines): aquí no hi ha dades en directe.</Buit></div>}
            </section>
          ))}
          <p className="petit muted" style={{ marginTop: 16 }}>
            «Ocupada»: porta tancada i presència. «Porta oberta»: el client surt o entra. «Sense dades»: fa més de 2 hores que la cabina no envia res.
            Les peces són les que les antenes han llegit dins la cabina el darrer minut.
          </p>
        </>
      )}
    </>
  );
}
