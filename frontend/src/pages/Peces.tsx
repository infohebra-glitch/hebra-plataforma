import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { analitica } from '../api/endpoints';
import type { ModelResum } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { MoltProvat, MostraPetita } from '../components/Insignies';
import { TaulaOrdenable, type Columna } from '../components/TaulaOrdenable';
import { TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { motiu } from '../lib/etiquetes';
import { enter, eur, pct, punts } from '../lib/format';
import { useApi } from '../lib/useApi';

const COLUMNES: Columna<ModelResum>[] = [
  { clau: 'nom', cap: 'Model', ordre: (m) => m.nom, cel: (m) => (
    <div style={{ display: 'grid', gap: 2 }}>
      <Link className="nom-model" to={`/peces/${encodeURIComponent(m.model)}`}>{m.nom}</Link>
      <span className="codi">{m.model}</span>
      {m.molt_provat_poc_venut && <span><MoltProvat /></span>}
    </div>
  ) },
  { clau: 'categoria', cap: 'Categoria', ordre: (m) => m.categoria, cel: (m) => <span style={{ whiteSpace: 'nowrap' }}>{m.categoria}</span> },
  { clau: 'proves', cap: 'Proves', n: true, ordre: (m) => m.proves, cel: (m) => enter(m.proves) },
  { clau: 'compres', cap: 'Compres', n: true, ordre: (m) => m.compres, cel: (m) => enter(m.compres) },
  { clau: 'conversio', cap: 'Conversió', n: true, ordre: (m) => m.conversio, cel: (m) => (
    <span style={{ display: 'inline-grid', gap: 2, justifyItems: 'end' }}><b>{pct(m.conversio)}</b><MostraPetita n={m.proves} /></span>
  ) },
  { clau: 'vs', cap: 'Vs categoria', n: true, ordre: (m) => (m.conversio !== null && m.conversio_categoria !== null ? m.conversio - m.conversio_categoria : null), cel: (m) => (
    <span title={`Categoria: ${pct(m.conversio_categoria)}`}>
      {m.conversio !== null && m.conversio_categoria !== null ? punts(m.conversio - m.conversio_categoria) : '—'}
      <span className="petit muted" style={{ display: 'block' }}>cat. {pct(m.conversio_categoria)}</span>
    </span>
  ) },
  { clau: 'motiu', cap: 'Motiu', ordre: (m) => m.motiu_principal, cel: (m) => motiu(m.motiu_principal) },
  { clau: 'estoc', cap: 'Estoc', n: true, ordre: (m) => m.estoc, cel: (m) => enter(m.estoc) },
  { clau: 'perduda', cap: 'Perduda', n: true, ordre: (m) => m.demanda_perduda, cel: (m) => enter(m.demanda_perduda) },
  { clau: 'preu', cap: 'Preu', n: true, ordre: (m) => m.preu, cel: (m) => eur(m.preu) },
];

export function Peces() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.models(filtre, s), [clau]);
  const [nomesAlerta, setNomesAlerta] = useState(false);
  const [cerca, setCerca] = useState('');
  const navega = useNavigate();
  return (
    <>
      <TitolPagina titol="Peces">Cada model amb les seves proves, compres i conversió comparada amb la de la seva categoria.</TitolPagina>
      <div className="fila" style={{ marginBottom: 12 }}>
        <label className="sr-only" htmlFor="cerca-model">Cerca un model</label>
        <input id="cerca-model" type="search" placeholder="Cerca per nom o codi" value={cerca} onChange={(e) => setCerca(e.target.value)} style={{ flex: '1 1 220px', maxWidth: 320 }} />
        <label className="interruptor"><input type="checkbox" checked={nomesAlerta} onChange={(e) => setNomesAlerta(e.target.checked)} />Només «molt provat, poc venut»</label>
      </div>
      <Consulta q={q} esquelet={<Esquelet tipus="taula" files={7} />}>
        {(r) => <Llista models={r.models} nomesAlerta={nomesAlerta} cerca={cerca} enClic={(m) => navega(`/peces/${encodeURIComponent(m.model)}`)} />}
      </Consulta>
      <p className="petit muted" style={{ marginTop: 12 }}>«Molt provat, poc venut»: moltes proves al període i conversió al quartil inferior de la seva categoria (o per sota del 60 % de la mitjana si la categoria té menys de 4 models). «Perduda»: peticions de talles que no hi eren. «Mostra petita»: menys de 30 proves, el percentatge encara pot variar molt.</p>
    </>
  );
}

function Llista({ models, nomesAlerta, cerca, enClic }: { models: ModelResum[]; nomesAlerta: boolean; cerca: string; enClic: (m: ModelResum) => void }) {
  const files = useMemo(() => {
    const c = cerca.trim().toLowerCase();
    return models.filter((m) => (!nomesAlerta || m.molt_provat_poc_venut) && (!c || m.nom.toLowerCase().includes(c) || m.model.toLowerCase().includes(c)));
  }, [models, nomesAlerta, cerca]);
  if (!models.length) return <div className="panell"><Buit titol="Encara no hi ha proves en aquest període">Quan els lectors de les cabines registrin proves, hi veuràs cada model. Prova un període més llarg o una altra botiga.</Buit></div>;
  if (!files.length) return <div className="panell"><Buit titol="Cap model coincideix amb el filtre">Treu el filtre o canvia la cerca.</Buit></div>;
  return <div className="panell" style={{ padding: 0 }}><TaulaOrdenable titol="Models" files={files} columnes={COLUMNES} clauFila={(m) => m.model} ordreInicial={{ clau: 'proves', desc: true }} enClic={enClic} /></div>;
}
