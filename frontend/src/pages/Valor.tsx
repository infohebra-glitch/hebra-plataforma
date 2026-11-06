import { useState, type FormEvent } from 'react';
import { analitica, operacio } from '../api/endpoints';
import type { Parametres } from '../api/types';
import { Consulta, Esquelet } from '../components/Estat';
import { Estimacio } from '../components/Insignies';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { insight } from '../lib/etiquetes';
import { enter, eur } from '../lib/format';
import { useApi } from '../lib/useApi';

const CAMPS: { clau: string; nom: string; unitat: string; ajuda: string }[] = [
  { clau: 'marge_peca', nom: 'Marge per peça', unitat: '€', ajuda: 'Marge brut mitjà d’una peça venuda.' },
  { clau: 'pvp_mitja', nom: 'PVP mitjà', unitat: '€', ajuda: 'Preu de venda mitjà, IVA inclòs.' },
  { clau: 'quota_mensual', nom: 'Quota mensual de Hebra', unitat: '€', ajuda: 'El que pagueu cada mes per botiga.' },
  { clau: 'n_molt_provat', nom: 'Proves per ser «molt provat»', unitat: 'per setmana', ajuda: 'Mínim de proves setmanals per marcar un model.' },
  { clau: 'dies_estoc_parat', nom: 'Dies per estoc parat', unitat: 'dies', ajuda: 'Sense proves ni vendes durant aquests dies.' },
  { clau: 'setmanes_cobertura', nom: 'Cobertura de risc', unitat: 'setmanes', ajuda: 'Estoc per a més setmanes que aquestes = risc de rebaixa.' },
  { clau: 'minuts_abandonada', nom: 'Minuts per peça abandonada', unitat: 'min', ajuda: 'Temps fora de la sala abans d’avisar.' },
];

export function Valor() {
  const { filtre, clau } = useFiltre();
  const qv = useApi((s) => analitica.valor(filtre, s), [clau]);
  const qp = useApi(() => operacio.parametres(), []);
  return (
    <>
      <TitolPagina titol="Valor estimat" senseperiode>
        Què hi pot guanyar la marca amb cada palanca, calculat amb els vostres paràmetres. Són <b>estimacions</b> per decidir on posar l’esforç, no resultats.
      </TitolPagina>
      <p className="avis-estimacio">Tots els imports d’aquesta pàgina són estimacions fetes amb fórmules i paràmetres que podeu canviar. No surten de vendes reals atribuïdes.</p>
      <Consulta q={qv} esquelet={<Esquelet tipus="taula" />}>
        {(v) => (
          <>
            {v.llindar_peces_mes !== null && (
              <div className="panell" style={{ marginTop: 16 }}>
                <p style={{ margin: 0 }}>Amb un marge de {eur(v.parametres.marge_peca)} per peça, Hebra es paga sola si ajuda a vendre <b>{enter(v.llindar_peces_mes)} peces més al mes</b> per botiga <Estimacio /></p>
              </div>
            )}
            <Seccio titol="Palanques">
              <ul className="llista-targetes reixa-2" style={{ display: 'grid' }}>
                {v.palanques.map((p) => (
                  <li key={p.palanca} className="targeta">
                    <div className="targeta-cap"><h3>{p.palanca}</h3>{p.es_estimacio && <Estimacio />}</div>
                    <p className="rajola-valor" style={{ margin: 0 }}>{p.valor_eur === null ? <span className="muted" style={{ fontSize: 18 }}>No es pot posar en euros</span> : <>≈ {eur(p.valor_eur)}</>}</p>
                    <p className="petit" style={{ margin: 0 }}><b>Fórmula:</b> {p.formula}</p>
                    <p className="petit muted" style={{ margin: 0 }}>{p.detall}</p>
                    <p className="petit muted" style={{ margin: 0 }}>Insights: {p.insights.map((i) => insight(i)).join(' · ')}</p>
                  </li>
                ))}
              </ul>
            </Seccio>
          </>
        )}
      </Consulta>
      <Seccio titol="Paràmetres" subtitol="Canvieu-los i les estimacions es tornen a calcular.">
        <Consulta q={qp} esquelet={<Esquelet tipus="taula" files={4} />}>
          {(p) => <FormParametres p={p} enDesat={() => { qp.recarrega(); qv.recarrega(); }} />}
        </Consulta>
      </Seccio>
    </>
  );
}

function FormParametres({ p, enDesat }: { p: Parametres; enDesat: () => void }) {
  const [estat, setEstat] = useState<{ tipus: 'ok' | 'error'; text: string } | null>(null);
  const [enviant, setEnviant] = useState(false);
  const envia = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const valors = { ...p.valors };
    for (const c of CAMPS) { const v = String(f.get(c.clau) ?? '').trim(); if (v) valors[c.clau] = v; }
    setEnviant(true); setEstat(null);
    try { await operacio.desaParametres({ botiga_id: p.botiga_id, valors }); setEstat({ tipus: 'ok', text: 'Paràmetres desats. Les estimacions s’han actualitzat.' }); enDesat(); }
    catch (err) { setEstat({ tipus: 'error', text: (err as Error).message }); }
    finally { setEnviant(false); }
  };
  return (
    <form className="panell formulari" onSubmit={envia}>
      <p className="petit muted" style={{ margin: 0 }}>Àmbit: {p.botiga_id === '*' ? 'totes les botigues' : p.botiga_id}</p>
      <div className="reixa-3">
        {CAMPS.map((c) => (
          <label key={c.clau} className="camp"><span>{c.nom} ({c.unitat})</span>
            <input name={c.clau} type="number" inputMode="decimal" min={0} step="any" defaultValue={p.valors[c.clau] ?? ''} />
            <small>{c.ajuda}</small>
          </label>
        ))}
      </div>
      <div className="fila">
        <button type="submit" className="boto-primari" disabled={enviant}>{enviant ? 'Desant…' : 'Desa els paràmetres'}</button>
        {estat && <span role="status" className={estat.tipus === 'ok' ? 'missatge-ok' : 'missatge-error'}>{estat.text}</span>}
      </div>
    </form>
  );
}
