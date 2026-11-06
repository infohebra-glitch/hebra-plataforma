import { useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { analitica, operacio } from '../api/endpoints';
import type { Decisio, EstatDecisio, NovaDecisio } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { ESTATS_DECISIO, INSIGHTS, insight } from '../lib/etiquetes';
import { diaCurt } from '../lib/format';
import { useApi } from '../lib/useApi';

const CLASSE: Record<EstatDecisio, string> = { proposada: 'insignia-alerta', acceptada: 'insignia-neutra', feta: 'insignia-bo', descartada: 'insignia-mostra' };

export function Decisions() {
  const { filtre, clau } = useFiltre();
  const q = useApi(() => operacio.decisions(filtre), [clau]);
  const models = useApi((s) => analitica.models(filtre, s), [clau]);
  const [filtreEstat, setFiltreEstat] = useState<EstatDecisio | ''>('');
  const [editant, setEditant] = useState<Decisio | null>(null);
  const [params] = useSearchParams();
  const dialeg = useRef<HTMLDialogElement>(null);
  const obre = (d: Decisio | null) => { setEditant(d); dialeg.current?.showModal(); };
  const canviaEstat = async (d: Decisio, estat: EstatDecisio) => { await operacio.canviaDecisio(d.id, { estat }); q.recarrega(); };

  return (
    <>
      <TitolPagina titol="Registre de decisions" senseperiode accions={<button type="button" className="boto-primari" onClick={() => obre(null)}>Nova decisió</button>}>
        Què hem decidit a partir de les dades, qui ho fa, per a quan i què n’ha sortit.
      </TitolPagina>
      <div className="fila" style={{ marginBottom: 12 }} role="group" aria-label="Filtra per estat">
        {(['', 'proposada', 'acceptada', 'feta', 'descartada'] as const).map((e) => (
          <button key={e || 'totes'} type="button" className={`boto-petit ${filtreEstat === e ? 'boto-primari' : ''}`} aria-pressed={filtreEstat === e} onClick={() => setFiltreEstat(e)}>
            {e ? ESTATS_DECISIO[e] : 'Totes'}
          </button>
        ))}
      </div>
      <Consulta q={q} esquelet={<Esquelet tipus="taula" files={4} />}>
        {(r) => {
          const files = r.decisions.filter((d) => !filtreEstat || d.estat === filtreEstat);
          if (!r.decisions.length) return <div className="panell"><Buit titol="Encara no hi ha cap decisió" accio={<button type="button" onClick={() => obre(null)}>Apunta la primera</button>}>Apunta aquí el que decidiu a partir d’un insight: així, al cap d’un mes, podreu veure si ha funcionat.</Buit></div>;
          if (!files.length) return <div className="panell"><Buit titol="Cap decisió en aquest estat">Tria un altre estat o «Totes».</Buit></div>;
          return (
            <ul className="llista-targetes">
              {files.map((d) => (
                <li key={d.id} className="targeta">
                  <div className="targeta-cap">
                    <h3>{d.titol}</h3>
                    <span className={`insignia ${CLASSE[d.estat] ?? 'insignia-mostra'}`}>{ESTATS_DECISIO[d.estat] ?? d.estat}</span>
                  </div>
                  {d.descripcio && <p style={{ margin: 0 }}>{d.descripcio}</p>}
                  <ul className="metadades">
                    {d.insight && <li><b>Insight:</b> {insight(d.insight)}</li>}
                    {d.model && <li><b>Peça:</b> <Link to={`/peces/${encodeURIComponent(d.model)}`}>{models.dades?.models.find((m) => m.model === d.model)?.nom ?? d.model}</Link></li>}
                    {d.responsable && <li><b>Qui:</b> {d.responsable}</li>}
                    {d.data_limit && <li><b>Per al</b> {diaCurt(d.data_limit)}</li>}
                    {d.experiment_id && <li><b>Prova:</b> <Link to="/origen">{d.experiment_id}</Link></li>}
                    <li><b>Creada el</b> {diaCurt(d.creada)}</li>
                  </ul>
                  {d.resultat && <p className="avis" style={{ margin: 0 }}><b>Resultat:</b> {d.resultat}</p>}
                  <div className="fila">
                    <label className="sr-only" htmlFor={`estat-${d.id}`}>Estat de «{d.titol}»</label>
                    <select id={`estat-${d.id}`} value={d.estat} onChange={(e) => canviaEstat(d, e.target.value as EstatDecisio)}>
                      {(Object.keys(ESTATS_DECISIO) as EstatDecisio[]).map((e) => <option key={e} value={e}>{ESTATS_DECISIO[e]}</option>)}
                    </select>
                    <button type="button" onClick={() => obre(d)}>Edita</button>
                  </div>
                </li>
              ))}
            </ul>
          );
        }}
      </Consulta>
      <dialog ref={dialeg} className="dialeg" aria-labelledby="titol-decisio" onClose={() => setEditant(null)}>
        <FormDecisio
          key={editant?.id ?? `nova-${params.get('model') ?? ''}`}
          inicial={editant}
          models={models.dades?.models.map((m) => ({ model: m.model, nom: m.nom })) ?? []}
          modelInicial={params.get('model') ?? ''}
          enTanca={(desat) => { dialeg.current?.close(); if (desat) q.recarrega(); }}
        />
      </dialog>
    </>
  );
}

function FormDecisio({ inicial, models, modelInicial, enTanca }: { inicial: Decisio | null; models: { model: string; nom: string }[]; modelInicial: string; enTanca: (desat: boolean) => void }) {
  const { filtre } = useFiltre();
  const [error, setError] = useState<string | null>(null);
  const [enviant, setEnviant] = useState(false);
  const envia = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const txt = (k: string) => { const v = String(f.get(k) ?? '').trim(); return v || null; };
    const d: NovaDecisio = {
      botiga_id: inicial?.botiga_id ?? filtre.botiga ?? null,
      titol: txt('titol') ?? '', descripcio: txt('descripcio') ?? '',
      insight: txt('insight') ?? null, model: txt('model'),
      responsable: txt('responsable'), data_limit: txt('data_limit'),
      estat: (txt('estat') as EstatDecisio) ?? 'proposada', experiment_id: inicial?.experiment_id ?? null, resultat: txt('resultat'),
    };
    if (!d.titol) { setError('Posa-hi un títol: què heu decidit?'); return; }
    setEnviant(true); setError(null);
    try {
      if (inicial) await operacio.canviaDecisio(inicial.id, d); else await operacio.creaDecisio(d);
      enTanca(true);
    } catch (err) { setError((err as Error).message); } finally { setEnviant(false); }
  };
  return (
    <form className="formulari" onSubmit={envia} noValidate>
      <h2 id="titol-decisio">{inicial ? 'Edita la decisió' : 'Nova decisió'}</h2>
      <label className="camp"><span>Què heu decidit</span><input name="titol" required defaultValue={inicial?.titol} placeholder="Reposar la camisa de lli en L" /></label>
      <label className="camp"><span>Per què (opcional)</span><textarea name="descripcio" defaultValue={inicial?.descripcio} /></label>
      <div className="dues">
        <label className="camp"><span>Insight que la motiva</span>
          <select name="insight" defaultValue={inicial?.insight ?? ''}><option value="">Cap</option>{Object.entries(INSIGHTS).map(([n, nom]) => <option key={n} value={n}>{n}. {nom}</option>)}</select>
        </label>
        <label className="camp"><span>Peça</span>
          <select name="model" defaultValue={inicial?.model ?? modelInicial}><option value="">Cap en concret</option>{models.map((m) => <option key={m.model} value={m.model}>{m.nom}</option>)}</select>
        </label>
        <label className="camp"><span>Responsable</span><input name="responsable" defaultValue={inicial?.responsable ?? ''} placeholder="Producte · Marta" /></label>
        <label className="camp"><span>Data límit</span><input name="data_limit" type="date" defaultValue={inicial?.data_limit ?? ''} /></label>
        <label className="camp"><span>Estat</span>
          <select name="estat" defaultValue={inicial?.estat ?? 'proposada'}>{(Object.keys(ESTATS_DECISIO) as EstatDecisio[]).map((e) => <option key={e} value={e}>{ESTATS_DECISIO[e]}</option>)}</select>
        </label>
      </div>
      <label className="camp"><span>Resultat</span><textarea name="resultat" defaultValue={inicial?.resultat ?? ''} placeholder="Què n’ha sortit? (quan se sàpiga)" /></label>
      {error && <p className="missatge-error" role="alert">{error}</p>}
      <div className="fila" style={{ justifyContent: 'flex-end' }}>
        <button type="button" onClick={() => enTanca(false)}>Cancel·la</button>
        <button type="submit" className="boto-primari" disabled={enviant}>{enviant ? 'Desant…' : inicial ? 'Desa els canvis' : 'Apunta la decisió'}</button>
      </div>
    </form>
  );
}
