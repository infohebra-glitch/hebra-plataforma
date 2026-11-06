import { useState } from 'react';
import { Link } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { CellaTalla, Talles as TTalles } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { CorbaTalles } from '../components/grafics/CorbaTalles';
import { MapaCalor } from '../components/grafics/MapaCalor';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { MOSTRA_MINIMA } from '../lib/etiquetes';
import { deCada, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

const ORDRE = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL'];
function ordenaTalles(t: string[]): string[] {
  return [...new Set(t)].sort((a, b) => {
    const ia = ORDRE.indexOf(a), ib = ORDRE.indexOf(b);
    if (ia >= 0 && ib >= 0) return ia - ib;
    if (ia >= 0) return -1;
    if (ib >= 0) return 1;
    return Number(a) - Number(b) || a.localeCompare(b);
  });
}

function Mapa({ taula, sistema }: { taula: CellaTalla[]; sistema: 'lletres' | 'numeros' }) {
  const files = taula.filter((c) => (ORDRE.includes(c.talla) ? sistema === 'lletres' : sistema === 'numeros'));
  if (!files.length) return null;
  const cats = [...new Set(files.map((c) => c.categoria))].sort((a, b) => a.localeCompare(b, 'ca'));
  const talles = ordenaTalles(files.map((c) => c.talla));
  const troba = (cat: string, t: string) => files.find((c) => c.categoria === cat && c.talla === t);
  return (
    <MapaCalor
      titol={`Conversió per categoria i talla (${sistema === 'lletres' ? 'talles en lletres' : 'talles numèriques'})`}
      capFila="Categoria"
      files={cats.map((c) => ({ clau: c, nom: c }))}
      columnes={talles.map((t) => ({ clau: t, nom: t }))}
      llegendaEscala={['menys conversió', 'més']}
      cel={(cat, t) => {
        const c = troba(cat, t);
        if (!c) return { v: null, text: <span className="muted">·</span>, titol: 'No es fa en aquesta talla' };
        const petita = c.proves < MOSTRA_MINIMA;
        return {
          v: c.conversio,
          titol: `${cat} ${t}: ${deCada(c.compres, c.proves)} proves acaben en compra${petita ? ' (mostra petita)' : ''}`,
          text: <>{pct(c.conversio)}<small style={{ display: 'block', fontSize: 11, opacity: 0.8 }}>{c.proves} pr.{petita ? '*' : ''}</small></>,
        };
      }}
    />
  );
}

function Corbes({ corba }: { corba: TTalles['corba'] }) {
  const [sel, setSel] = useState(corba[0]?.model ?? '');
  const c = corba.find((x) => x.model === sel) ?? corba[0];
  if (!c) return <Buit titol="Encara no hi ha prou dades">Calen proves i compres per talla per proposar una corba.</Buit>;
  return (
    <div className="reixa-2">
      <div className="panell">
        <label className="camp" style={{ marginBottom: 12, maxWidth: 320 }}><span>Model</span>
          <select value={c.model} onChange={(e) => setSel(e.target.value)}>
            {corba.map((x) => <option key={x.model} value={x.model}>{x.nom}</option>)}
          </select>
        </label>
        <CorbaTalles titol={`Corba proposada per a ${c.nom}`} files={c.talles} />
      </div>
      <div className="panell" style={{ padding: 0 }}>
        <div className="taula-wrap">
          <table>
            <caption className="sr-only">Corba de talles de {c.nom}</caption>
            <thead><tr><th scope="col">Talla</th><th scope="col" className="n">% provat</th><th scope="col" className="n">% comprat</th><th scope="col" className="n">% estoc ara</th><th scope="col" className="n">Proposta</th></tr></thead>
            <tbody>
              {c.talles.map((t) => (
                <tr key={t.talla}><td><b>{t.talla}</b></td><td className="n">{pct(t.pct_proves)}</td><td className="n">{pct(t.pct_compres)}</td><td className="n">{pct(t.pct_estoc)}</td><td className="n"><b>{pct(t.proposta_pct)}</b></td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="petit muted" style={{ padding: '8px 12px 12px', margin: 0 }}>Proposta = 70 % del que es compra + 30 % del que es prova, arrodonit a 5 punts. És un punt de partida per a la propera comanda, no una ordre.</p>
      </div>
    </div>
  );
}

export function Talles() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.talles(filtre, s), [clau]);
  return (
    <>
      <TitolPagina titol="Talles">Quines talles es proven i no es venen, i quina corba demanar la propera vegada.</TitolPagina>
      <Consulta q={q} esquelet={<Esquelet tipus="taula" />}>
        {(t) => (
          <>
            <Seccio titol="La talla que no quadra" subtitol="Talles que es venen molt menys que la resta de talles del mateix model.">
              {t.no_quadra.length ? (
                <ul className="llista-targetes">
                  {t.no_quadra.map((n) => (
                    <li key={`${n.model}-${n.talla}`} className="targeta accio-setmana">
                      <div className="targeta-cap"><h3>{n.nom} en {n.talla}</h3><Link to={`/peces/${encodeURIComponent(n.model)}`}>Veure la peça</Link></div>
                      <p style={{ margin: 0 }}>{n.text}</p>
                      <p className="petit muted" style={{ margin: 0 }}>Conversió de la {n.talla}: <b>{pct(n.conversio)}</b> · resta de talles: <b>{pct(n.conversio_resta_talles)}</b></p>
                    </li>
                  ))}
                </ul>
              ) : <div className="panell"><Buit titol="Cap talla fora de lloc">En aquest període, cap talla queda clarament per sota de les altres del seu model.</Buit></div>}
            </Seccio>
            <Seccio titol="Conversió per categoria i talla" subtitol={<>Com més fosc, més proves acaben en compra. Sota cada percentatge, el nombre de proves; amb asterisc, menys de {MOSTRA_MINIMA} (mostra petita).</>}>
              {t.taula.length ? (
                <div className="reixa-2">
                  <div className="panell"><Mapa taula={t.taula} sistema="lletres" /></div>
                  <div className="panell"><Mapa taula={t.taula} sistema="numeros" /></div>
                </div>
              ) : <div className="panell"><Buit titol="Encara no hi ha proves">Quan n’hi hagi, veuràs aquí la conversió de cada talla.</Buit></div>}
            </Seccio>
            <Seccio titol="Corba de talles proposada" subtitol="Per a cada model: percentatge de proves, de compres i d’estoc actual per talla, i la corba que en surt.">
              <Corbes corba={t.corba} />
            </Seccio>
          </>
        )}
      </Consulta>
    </>
  );
}
