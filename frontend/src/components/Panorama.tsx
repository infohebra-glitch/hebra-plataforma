/**
 * v0.5 «Panorama» del Resum: els gràfics que fan servir les eines de provador del sector
 * (embut del toc a la compra, ocupació per dia i hora, conversió per categoria, temps a la cabina,
 * peces per sessió, motius) i la galeria de les peces que mouen la botiga, amb la seva foto.
 */
import { Link } from 'react-router-dom';
import type { Panorama as TPanorama } from '../api/types';
import { DIES_SETMANA_LLARG, enter, eur, pct } from '../lib/format';
import { MostraPetita } from './Insignies';
import { FotoPeca, Sparkline } from './Peca';
import { Seccio } from './TitolPagina';
import { Columnes } from './grafics/Columnes';
import { Donut } from './grafics/Donut';
import { Embut } from './grafics/Embut';
import { MapaCalor } from './grafics/MapaCalor';

const DIES = ['dl.', 'dt.', 'dc.', 'dj.', 'dv.', 'ds.', 'dg.'];

function franjaPunta(p: TPanorama): string | null {
  let best = { v: 0, d: 0, h: 0 };
  p.mapa_calor.proves.forEach((fila, d) => fila.forEach((v, i) => { if (v > best.v) best = { v, d, h: p.mapa_calor.hores[i] }; }));
  return best.v ? `${DIES_SETMANA_LLARG[best.d]} de ${best.h} a ${best.h + 1} h` : null;
}

function notaEmbut(p: TPanorama, clau: string): string | undefined {
  const n = (c: string) => p.embut.find((e) => e.clau === c)?.n ?? 0;
  if (clau === 'peticions') return `${pct(n('proves') ? n('peticions') / n('proves') : null)} de les proves demanen una altra talla des de la cabina`;
  if (clau === 'compres') return `${pct(n('proves') ? n('compres') / n('proves') : null)} de les peces provades acaben comprades`;
  if (clau === 'proves') return n('tocs') ? `${pct(n('proves') / n('tocs'))} dels tocs a la fitxa` : 'peces que han entrat a la cabina';
  return 'punt de partida';
}

export function GaleriaPeces({ peces, max = 8 }: { peces: TPanorama['peces']; max?: number }) {
  return (
    <ul className="galeria-peces">
      {peces.slice(0, max).map((p, i) => (
        <li key={p.model}>
          <Link to={`/peces/${encodeURIComponent(p.model)}`} className="targeta-peca">
            <span className="posicio" aria-label={`Posició ${i + 1}`}>{i + 1}</span>
            <FotoPeca src={p.imatge} nom={`${p.nom}${p.color ? `, ${p.color}` : ''}`} />
            <span className="cos">
              <span className="nom">{p.nom}</span>
              <span className="petit muted">{[p.color, p.preu !== null ? eur(p.preu) : null].filter(Boolean).join(' · ')}</span>
              <span className="xifres">
                <span><b>{enter(p.proves)}</b> proves</span>
                <span><b>{pct(p.conversio)}</b> conv. <MostraPetita n={p.proves} /></span>
              </span>
              <Sparkline valors={p.serie} titol={`Proves per dia de ${p.nom}`} />
              <span className="petit muted">
                {enter(p.unitats_venudes)} venudes
                {p.cobertura_setmanes !== null && <> · estoc per {String(p.cobertura_setmanes).replace('.', ',')} setm.</>}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function Panorama({ p }: { p: TPanorama }) {
  const punta = franjaPunta(p);
  const maxCat = Math.max(1, ...p.per_categoria.map((c) => c.proves));
  return (
    <>
      <Seccio titol="Les peces que mouen la botiga" subtitol="Les més provades del període, amb la conversió, la tendència diària i quantes setmanes d’estoc queden al ritme de venda actual.">
        {p.peces.length ? <GaleriaPeces peces={p.peces} /> : <p className="muted">Encara no hi ha peces provades en aquest període.</p>}
      </Seccio>

      <div className="reixa-2">
        <Seccio titol="Del toc a la compra" subtitol="Quantes vegades toquen la fitxa NFC, quantes peces entren a la cabina i quantes acaben comprades.">
          <div className="panell"><Embut titol="Embut del toc a la compra" graons={p.embut.map((e) => ({ ...e, nota: notaEmbut(p, e.clau) }))} /></div>
        </Seccio>
        <Seccio titol="Conversió per categoria" subtitol="Quina part de les proves de cada categoria acaba en compra.">
          <div className="panell">
            <ul className="barres barres-conversio">
              {p.per_categoria.map((c) => (
                <li key={c.categoria}>
                  <span>{c.categoria}</span>
                  <span className="pista" aria-hidden="true">
                    <span className="ple fons" style={{ width: `${(c.proves / maxCat) * 100}%` }} />
                    <span className="ple" style={{ width: `${(c.compres / maxCat) * 100}%` }} />
                  </span>
                  <span className="valor"><b>{pct(c.conversio)}</b><small> · {enter(c.compres)} de {enter(c.proves)}</small></span>
                </li>
              ))}
            </ul>
            <p className="petit muted" style={{ marginTop: 10 }}><span className="clau-quadre" style={{ background: 'var(--serie-1)' }} /> comprades <span className="clau-quadre" style={{ background: 'var(--accent-soft)', marginLeft: 10 }} /> provades</p>
          </div>
        </Seccio>
      </div>

      <Seccio titol="Quan s’omplen els provadors" subtitol={<>Proves per dia de la setmana i hora.{punta && <> La franja amb més proves: <b>{punta}</b>. Útil per posar-hi més gent o reposar abans.</>}</>}>
        <div className="panell">
          <MapaCalor
            titol="Proves per dia de la setmana i hora"
            files={DIES.map((d, i) => ({ clau: String(i), nom: d })).filter((_, i) => p.mapa_calor.proves[i].some((v) => v > 0))}
            columnes={p.mapa_calor.hores.filter((_, i) => p.mapa_calor.proves.some((f) => f[i] > 0)).map((h) => ({ clau: String(h), nom: `${h} h` }))}
            cel={(f, c) => {
              const v = p.mapa_calor.proves[Number(f)][p.mapa_calor.hores.indexOf(Number(c))];
              return { v, text: v ? enter(v) : '', titol: `${DIES_SETMANA_LLARG[Number(f)]}, ${c} h: ${enter(v)} proves` };
            }}
            llegendaEscala={['menys', 'més proves']}
            capFila="Hora"
          />
        </div>
      </Seccio>

      <div className="reixa-3">
        <Seccio titol="Temps a la cabina" subtitol={p.temps_cabina.mediana_minuts !== null ? <>Mediana de <b>{String(p.temps_cabina.mediana_minuts).replace('.', ',')} min</b> per sessió.</> : 'Durada de cada sessió amb alguna prova.'}>
          <div className="panell">
            <Columnes titol="Sessions per durada" nomEixX="Minuts" alcada={190}
              x={p.temps_cabina.trams.map((t) => (t.fins === null ? `${t.des}+` : `${t.des}-${t.fins}`))}
              series={[{ nom: 'Sessions', valors: p.temps_cabina.trams.map((t) => t.sessions) }]} />
          </div>
        </Seccio>
        <Seccio titol="Peces per sessió" subtitol="Quantes peces s’emporten a la cabina cada vegada.">
          <div className="panell">
            <Columnes titol="Sessions segons el nombre de peces" nomEixX="Peces" alcada={190}
              x={p.peces_per_sessio.map((x) => String(x.peces))}
              series={[{ nom: 'Sessions', valors: p.peces_per_sessio.map((x) => x.sessions) }]} />
          </div>
        </Seccio>
        <Seccio titol="Per què no se l’emporten" subtitol="Respostes a la fitxa NFC.">
          <div className="panell">
            {p.motius.length ? <Donut titol="Motius de no compra" etiquetes={p.motius.map((m) => m.nom)} valors={p.motius.map((m) => m.n)} /> : <p className="muted">Encara cap resposta.</p>}
          </div>
        </Seccio>
      </div>
    </>
  );
}
