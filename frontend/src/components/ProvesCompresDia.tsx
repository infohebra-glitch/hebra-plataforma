/**
 * Proves i compres per dia, amb la possibilitat de comparar-les (període anterior, l'any passat o una
 * col·lecció), de mirar només una franja del dia i de filtrar per les condicions del dia (pluja, festiu...).
 * Les condicions les marca la botiga o la marca a «Connexions i dades»; més endavant es podran omplir
 * soles amb dades de meteorologia.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { Comparativa, Resum as TResum } from '../api/types';
import { useFiltre } from '../context/Filtre';
import { diaCurt, diaLlarg, diaSetmana, enter, pct, punts } from '../lib/format';
import { useApi } from '../lib/useApi';
import { SerieTemporal, type Serie } from './grafics/SerieTemporal';

const FRANGES: Record<string, string> = { mati: 'Matí (10-14 h)', migdia: 'Migdia (14-17 h)', tarda: 'Tarda (17-21 h)' };
const NOM_CONDICIO: Record<string, string> = {
  pluja: 'pluja', calor: 'calor', fred: 'fred', festiu: 'festiu', rebaixes: 'rebaixes', esdeveniment: 'esdeveniment',
};

function ambQue(compara: string, etiqueta: string): string {
  if (compara === 'anterior') return 'al període anterior';
  if (compara === 'any') return "a l'any passat";
  return `a la col·lecció «${etiqueta}»`;
}

function lectura(c: Comparativa, franja: string, condicio: string, compara: string): string {
  const t = c.total;
  if (!t.proves) return 'No hi ha proves amb aquests filtres.';
  const on = [franja && FRANGES[franja].toLowerCase(), condicio && (condicio.startsWith('!') ? `dies sense ${condicio.slice(1)}` : `dies amb ${condicio}`)]
    .filter(Boolean).join(', ');
  let txt = `${on ? `En ${on}: ` : ''}${enter(t.proves)} proves en ${t.dies} ${t.dies === 1 ? 'dia' : 'dies'} (${enter(Math.round(t.proves / Math.max(1, t.dies)))} per dia), `
    + `${enter(t.compres)} acaben en compra: ${pct(t.conversio)}.`;
  const k = c.comparacio;
  if (k && k.total.proves) {
    const dp = t.proves / Math.max(1, t.dies) / (k.total.proves / Math.max(1, k.total.dies)) - 1;
    const dc = (t.conversio ?? 0) - (k.total.conversio ?? 0);
    txt += ` Respecte ${ambQue(compara, k.etiqueta)} (${diaCurt(k.des)}–${diaCurt(k.fins)}): ${dp >= 0 ? '+' : '−'}${pct(Math.abs(dp))} proves per dia i ${punts(dc)} de conversió.`;
    if (Math.abs(dc) >= 0.03) {
      txt += dc < 0
        ? ' Es prova però es compra menys: mira quins models han baixat a «Peces» i els motius de no compra.'
        : ' La conversió puja: mira a «Peces» quins models ho expliquen i si n\'hi ha prou estoc.';
    } else if (Math.abs(dp) >= 0.15) {
      txt += dp > 0 ? ' Hi ha més gent provant-se roba amb la mateixa conversió: revisa els torns a les hores punta.' : ' Menys proves amb la mateixa conversió: és trànsit, no producte.';
    } else txt += ' Sense canvis importants.';
  } else if (k) txt += ` No hi ha dades per comparar ${ambQue(compara, k.etiqueta).replace(/^a(l)? /, (x) => (x === 'al ' ? 'del ' : 'de '))}.`;
  return txt;
}

export function ProvesCompresDia({ r }: { r: TResum }) {
  const { filtre, clau } = useFiltre();
  const [compara, setCompara] = useState('');
  const [franja, setFranja] = useState('');
  const [condicio, setCondicio] = useState('');
  const colleccions = useApi((s) => analitica.colleccions(s), []);
  const [cmp, colleccio] = compara.startsWith('c') ? ['colleccio', Number(compara.slice(1))] : [compara, undefined];
  const filtrat = !!(compara || franja || condicio);
  const q = useApi((s) => (filtrat
    ? analitica.comparativa(filtre, { compara: cmp || undefined, colleccio, franja: franja || undefined, condicio: condicio || undefined }, s)
    : Promise.resolve(null)), [clau, compara, franja, condicio]);
  const c = q.dades;
  const dies = c ? c.dies : r.serie_diaria.map((d) => ({ ...d, condicions: [] as string[], compleix: true }));
  const etiq = c?.comparacio?.etiqueta;
  const series: Serie[] = [
    { clau: 'proves', nom: 'Proves', classe: 's1', valors: dies.map((d) => d.proves) },
    { clau: 'compres', nom: 'Compres després de provar', classe: 's2', valors: dies.map((d) => d.compres) },
  ];
  // Amb un filtre de condicions, els dies de pluja d'un període i de l'altre no cauen el mateix dia de la
  // setmana: es comparen els totals (a sobre), no dia a dia.
  if (c?.comparacio && !condicio) {
    const alinea = (k: 'proves' | 'compres') => dies.map((_, i) => c.comparacio!.dies[i]?.[k] ?? null);
    series.push({ clau: 'proves-cmp', nom: `Proves · ${etiq}`, classe: 's1', valors: alinea('proves'), discontinua: true });
    series.push({ clau: 'compres-cmp', nom: `Compres · ${etiq}`, classe: 's2', valors: alinea('compres'), discontinua: true });
  }
  const condicions = c?.condicions_disponibles ?? ['pluja', 'calor', 'fred', 'festiu', 'rebaixes', 'esdeveniment'];
  return (
    <div className="panell">
      <div className="comparativa-controls">
        <label>Compara amb
          <select value={compara} onChange={(e) => setCompara(e.target.value)}>
            <option value="">No comparis</option>
            <option value="anterior">El període anterior</option>
            <option value="any">El mateix període de l'any passat</option>
            {(colleccions.dades ?? []).map((k) => <option key={k.id} value={`c${k.id}`}>Col·lecció: {k.nom}</option>)}
          </select>
        </label>
        <label>Hores del dia
          <select value={franja} onChange={(e) => setFranja(e.target.value)}>
            <option value="">Tot el dia</option>
            {Object.entries(FRANGES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Condicions del dia
          <select value={condicio} onChange={(e) => setCondicio(e.target.value)}>
            <option value="">Tots els dies</option>
            {condicions.map((k) => <option key={k} value={k}>Dies amb {NOM_CONDICIO[k] ?? k}</option>)}
            {condicions.map((k) => <option key={`!${k}`} value={`!${k}`}>Dies sense {NOM_CONDICIO[k] ?? k}</option>)}
          </select>
        </label>
        <Link className="petit" to="/dades#condicions">Marca dies de pluja, festius o col·leccions</Link>
      </div>
      {c && (
        <div className="comparativa-resum" aria-live="polite">
          <div><b>{enter(c.total.proves)}</b><span>proves en {c.total.dies} dies</span></div>
          <div><b>{pct(c.total.conversio)}</b><span>de les proves acaben en compra</span></div>
          {c.comparacio && <div><b>{enter(c.comparacio.total.proves)}</b><span>proves · {etiq}</span></div>}
          {c.comparacio && (() => {
            const d = (c.total.conversio ?? 0) - (c.comparacio.total.conversio ?? 0);
            return <div><b className={d > 0.005 ? 'bo' : d < -0.005 ? 'dolent' : ''}>{punts(d)}</b><span>conversió vs {etiq?.toLowerCase()}</span></div>;
          })()}
        </div>
      )}
      {q.error && <p className="error petit" role="alert">{q.error.message}</p>}
      {dies.length ? (
        <SerieTemporal
          titol="Proves i compres per dia"
          x={dies.map((d) => d.data)}
          etiquetaX={(i) => (dies.length > 10 ? diaCurt(dies[i].data) : diaSetmana(dies[i].data))}
          detallX={(i) => `${diaLlarg(dies[i].data)}${dies[i].condicions.length ? ` · ${dies[i].condicions.join(', ')}` : ''}`}
          series={series}
          formatY={enter}
          formatValor={(v, s, i) => {
            if (v === null) return '—';
            if (s.clau === 'compres') return `${enter(v)} (${pct(dies[i].conversio)})`;
            return enter(v);
          }}
          bandes={c ? undefined : r.serie_diaria.map((d) => d.grup_origen === 'amb')}
          nomBanda={c ? undefined : 'Dia amb origen visible'}
        />
      ) : <p className="muted">Encara no hi ha dies amb dades en aquest període.</p>}
      {c && <p className="comparativa-lectura">{lectura(c, franja, condicio, cmp)}</p>}
    </div>
  );
}
