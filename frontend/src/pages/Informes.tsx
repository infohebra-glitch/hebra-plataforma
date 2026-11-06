/** Informes (E.5): lliurats per data, amb filtre per tipus; programació (marca+); «Genera ara». */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { desaBlob } from '../api/client';
import { informes } from '../api/endpoints';
import type { InformeLliurat, NovaProgramacio, Programacio, TipusInforme } from '../api/types';
import { DialegCorreu } from '../components/DialegCorreu';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { Icona } from '../components/Icones';
import { TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { INFORMES } from '../lib/etiquetes';
import { DIES_SETMANA_LLARG, dataLocal, diaCurt, diaLlarg, hora, rang } from '../lib/format';
import { descriuProgramacio, llegeixCorreus, properaExecucio, recurrencia, textPropera } from '../lib/programacio';
import { useApi } from '../lib/useApi';

export const nomInforme = (t: string) => INFORMES.find((i) => i.tipus === t)?.nom ?? t;
const fDiaSetmana = new Intl.DateTimeFormat('ca-ES', { weekday: 'long', day: 'numeric', month: 'short' });

/** Títol d'un lliurat segons el seu període. */
export function periodeLliurat(l: Pick<InformeLliurat, 'tipus' | 'des' | 'fins'>): string {
  const t = l.tipus === 'diari' || l.des === l.fins ? fDiaSetmana.format(dataLocal(l.des))
    : l.tipus === 'mensual' ? new Intl.DateTimeFormat('ca-ES', { month: 'long', year: 'numeric' }).format(dataLocal(l.des))
      : rang(l.des, l.fins);
  return t.charAt(0).toUpperCase() + t.slice(1);
}
export const titolLliurat = (l: Pick<InformeLliurat, 'tipus' | 'des' | 'fins'>): string => `${nomInforme(l.tipus)} · ${periodeLliurat(l).replace(/^./, (c) => c.toLowerCase())}`;

export function EstatEnviament({ l }: { l: InformeLliurat }) {
  if (l.estat_enviament === 'enviat') return <span className="insignia insignia-bo" title={l.enviat_a.join(', ')}>✓ Enviat a {l.enviat_a.length === 1 ? l.enviat_a[0] : `${l.enviat_a.length} persones`}</span>;
  if (l.estat_enviament === 'error') return <span className="insignia insignia-critic">✕ No s’ha pogut enviar</span>;
  return <span className="insignia insignia-mostra">No enviat</span>;
}

export function Informes() {
  const { pot } = useSessio();
  const marca = pot('admin', 'marca');
  const [params, setParams] = useSearchParams();
  const vista = params.get('vista') === 'programacio' && marca ? 'programacio' : 'lliurats';
  const [genera, setGenera] = useState(false);
  const pestanya = (v: 'lliurats' | 'programacio', nom: string) => (
    <button type="button" role="tab" id={`tab-${v}`} aria-selected={vista === v} aria-controls={`panell-${v}`} className={`pestanya${vista === v ? ' activa' : ''}`}
      onClick={() => setParams(v === 'lliurats' ? {} : { vista: v }, { replace: true })}>{nom}</button>
  );
  return (
    <>
      <TitolPagina titol="Informes" senseperiode accions={marca ? <button type="button" className="boto-primari" onClick={() => setGenera(true)}>Genera ara</button> : undefined}>
        Els informes que Hebra ha preparat i enviat, ordenats per data. Obre’n un per veure’l, descarregar-lo en PDF o reenviar-lo.
      </TitolPagina>
      {marca && (
        <div className="pestanyes" role="tablist" aria-label="Informes">
          {pestanya('lliurats', 'Lliurats')}
          {pestanya('programacio', 'Programació')}
        </div>
      )}
      <div role={marca ? 'tabpanel' : undefined} id={`panell-${vista}`} aria-labelledby={marca ? `tab-${vista}` : undefined}>
        {vista === 'lliurats' ? <Lliurats /> : <ProgramacioInformes />}
      </div>
      {marca && <DialegGenera obert={genera} enTanca={() => setGenera(false)} />}
    </>
  );
}

function Lliurats() {
  const { filtre } = useFiltre();
  const { botigues } = useSessio();
  const [tipus, setTipus] = useState<TipusInforme | ''>('');
  const q = useApi((s) => informes.lliurats(filtre.botiga, tipus || undefined, s), [filtre.botiga, tipus]);
  const [correu, setCorreu] = useState<InformeLliurat | null>(null);
  const [errorPdf, setErrorPdf] = useState<string | null>(null);
  const nomBotiga = (id: string | null) => (id ? botigues.find((b) => b.id === id)?.nom ?? id : 'Totes les botigues');
  const pdf = async (l: InformeLliurat) => {
    setErrorPdf(null);
    try { desaBlob(await informes.pdfLliurat(l.id), `hebra-${l.tipus}-${l.des}.pdf`); } catch (e) { setErrorPdf((e as Error).message); }
  };
  return (
    <>
      <div className="fila" role="group" aria-label="Filtra per tipus d’informe" style={{ marginBottom: 12 }}>
        {(['', ...INFORMES.map((i) => i.tipus)] as const).map((t) => (
          <button key={t || 'tots'} type="button" className={`boto-petit ${tipus === t ? 'boto-primari' : ''}`} aria-pressed={tipus === t} onClick={() => setTipus(t)}>{t ? nomInforme(t) : 'Tots'}</button>
        ))}
      </div>
      {errorPdf && <p className="missatge-error" role="alert">No s’ha pogut descarregar el PDF: {errorPdf}</p>}
      <Consulta q={q} esquelet={<Esquelet tipus="taula" files={6} />}>
        {(r) => {
          if (!r.lliurats.length) return <div className="panell"><Buit titol={tipus ? `Cap ${nomInforme(tipus).toLowerCase()} lliurat` : 'Encara cap informe lliurat'}>Els informes programats apareixeran aquí quan es generin. També en pots generar un ara.</Buit></div>;
          const grups = new Map<string, InformeLliurat[]>();
          for (const l of r.lliurats) { const k = l.generat.slice(0, 7); grups.set(k, [...(grups.get(k) ?? []), l]); }
          return [...grups.entries()].map(([mes, ll]) => (
            <section key={mes} aria-label={mes} style={{ marginBottom: 16 }}>
              <h2 className="grup-data">{new Intl.DateTimeFormat('ca-ES', { month: 'long', year: 'numeric' }).format(dataLocal(`${mes}-01`))}</h2>
              <ul className="llista-lliurats">
                {ll.map((l) => (
                  <li key={l.id} className="lliurat">
                    <div className="lliurat-cos">
                      <span className={`insignia tipus-${l.tipus}`}>{nomInforme(l.tipus)}</span>
                      <Link className="nom-model" to={`/informes/lliurats/${l.id}`} aria-label={`Obre ${titolLliurat(l)}`}>{periodeLliurat(l)}</Link>
                      <span className="petit muted">{nomBotiga(l.botiga_id)} · generat el {diaCurt(l.generat)} a les {hora(l.generat)}</span>
                    </div>
                    <EstatEnviament l={l} />
                    <div className="fila lliurat-accions">
                      <button type="button" className="boto-petit" onClick={() => pdf(l)} aria-label={`Descarrega el PDF de ${titolLliurat(l)}`}><Icona nom="baixa" mida={16} />PDF</button>
                      <button type="button" className="boto-petit" onClick={() => setCorreu(l)} aria-label={`Envia per correu ${titolLliurat(l)}`}><Icona nom="correu" mida={16} />Envia</button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ));
        }}
      </Consulta>
      <DialegCorreu obert={!!correu} titol={correu ? titolLliurat(correu) : ''} inicial={correu?.enviat_a} enTanca={() => { setCorreu(null); q.recarrega(); }}
        envia={(d) => informes.enviaLliurat(correu!.id, d)} />
    </>
  );
}

function DialegGenera({ obert, enTanca }: { obert: boolean; enTanca: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const { filtre, periode } = useFiltre();
  const { botigues } = useSessio();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [enCurs, setEnCurs] = useState(false);
  useEffect(() => { const d = ref.current; if (obert && d && !d.open) { setError(null); d.showModal(); } if (!obert && d?.open) d.close(); }, [obert]);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const des = String(f.get('des')), fins = String(f.get('fins'));
    if (!des || !fins || des > fins) { setError('Tria un període vàlid: la data d’inici ha de ser abans de la de final.'); return; }
    setEnCurs(true); setError(null);
    try {
      const l = await informes.generaAra({ tipus: f.get('tipus') as TipusInforme, botiga: String(f.get('botiga')) || null, des, fins });
      enTanca(); nav(`/informes/lliurats/${l.id}`);
    } catch (err) { setError((err as Error).message); } finally { setEnCurs(false); }
  };
  return (
    <dialog ref={ref} className="dialeg" aria-labelledby="titol-genera" onClose={enTanca}>
      <form className="formulari" onSubmit={submit} noValidate>
        <h2 id="titol-genera">Genera un informe ara</h2>
        <p className="muted" style={{ margin: 0 }}>Es guarda a la llista de lliurats (no s’envia a ningú fins que no ho demanis).</p>
        <label className="camp"><span>Tipus</span><select name="tipus" defaultValue="setmanal">{INFORMES.map((i) => <option key={i.tipus} value={i.tipus}>{i.nom} · {i.per}</option>)}</select></label>
        <label className="camp"><span>Botiga</span><select name="botiga" defaultValue={filtre.botiga ?? ''}><option value="">Totes les botigues</option>{botigues.map((b) => <option key={b.id} value={b.id}>{b.nom}</option>)}</select></label>
        <div className="dues">
          <label className="camp"><span>Des del</span><input type="date" name="des" defaultValue={periode.des} required /></label>
          <label className="camp"><span>Fins al</span><input type="date" name="fins" defaultValue={periode.fins} required /></label>
        </div>
        {error && <p className="missatge-error" role="alert">{error}</p>}
        <div className="fila" style={{ justifyContent: 'flex-end' }}>
          <button type="button" onClick={enTanca}>Cancel·la</button>
          <button type="submit" className="boto-primari" disabled={enCurs}>{enCurs ? 'Generant…' : 'Genera'}</button>
        </div>
      </form>
    </dialog>
  );
}

function ProgramacioInformes() {
  const { filtre } = useFiltre();
  const { botigues } = useSessio();
  const q = useApi((s) => informes.programacio(filtre.botiga, s), [filtre.botiga]);
  const [editant, setEditant] = useState<Programacio | 'nova' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nomBotiga = (id: string | null) => (id ? botigues.find((b) => b.id === id)?.nom ?? id : 'Totes les botigues');
  const commuta = async (p: Programacio) => { setError(null); try { await informes.canviaProgramacio(p.id, { actiu: !p.actiu }); q.recarrega(); } catch (e) { setError((e as Error).message); } };
  const esborra = async (p: Programacio) => {
    if (!window.confirm(`Vols esborrar la programació «${nomInforme(p.tipus)}»? Els informes ja lliurats es mantenen.`)) return;
    setError(null);
    try { await informes.esborraProgramacio(p.id); q.recarrega(); } catch (e) { setError((e as Error).message); }
  };
  return (
    <>
      <div className="fila entre" style={{ marginBottom: 12 }}>
        <p className="muted" style={{ margin: 0, maxWidth: '70ch' }}>Quins informes es generen sols, quan, i a qui s’envien. Si el correu no està configurat al servidor, es generen igualment i queden a «Lliurats».</p>
        <button type="button" onClick={() => setEditant('nova')}>Nova programació</button>
      </div>
      {error && <p className="missatge-error" role="alert">{error}</p>}
      <Consulta q={q} esquelet={<Esquelet tipus="taula" files={4} />}>
        {(r) => r.programacions.length ? (
          <ul className="llista-targetes reixa-2" style={{ display: 'grid' }}>
            {r.programacions.map((p) => (
              <li key={p.id} className={`targeta${p.actiu ? '' : ' desactivada'}`}>
                <div className="targeta-cap">
                  <h3>{nomInforme(p.tipus)}</h3>
                  <span className={`insignia ${p.actiu ? 'insignia-bo' : 'insignia-mostra'}`}>{p.actiu ? 'Activa' : 'Aturada'}</span>
                </div>
                <p style={{ margin: 0 }}>{descriuProgramacio(p)}</p>
                <ul className="metadades">
                  <li><b>Botiga:</b> {nomBotiga(p.botiga_id)}</li>
                  <li><b>Propera:</b> {p.actiu ? textPropera(p.propera ? new Date(p.propera) : properaExecucio(p)) : '—'}</li>
                </ul>
                <p className="petit" style={{ margin: 0 }}><b>A qui:</b> {p.destinataris.length ? p.destinataris.join(', ') : <span className="muted">ningú (només es guarda)</span>}</p>
                <div className="fila">
                  <label className="interruptor"><input type="checkbox" checked={p.actiu} onChange={() => commuta(p)} />Activa</label>
                  <span style={{ flex: 1 }} />
                  <button type="button" className="boto-petit" onClick={() => setEditant(p)}>Edita</button>
                  <button type="button" className="boto-petit boto-fantasma" onClick={() => esborra(p)}>Esborra</button>
                </div>
              </li>
            ))}
          </ul>
        ) : <div className="panell"><Buit titol="Cap informe programat" accio={<button type="button" onClick={() => setEditant('nova')}>Programa’n un</button>}>Per exemple, el resum diari a les 8 del matí per a l’encarregada.</Buit></div>}
      </Consulta>
      <DialegProgramacio editant={editant} enTanca={(desat) => { setEditant(null); if (desat) q.recarrega(); }} />
    </>
  );
}

function DialegProgramacio({ editant, enTanca }: { editant: Programacio | 'nova' | null; enTanca: (desat: boolean) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const { botigues } = useSessio();
  const { filtre } = useFiltre();
  const inicial: NovaProgramacio = editant && editant !== 'nova'
    ? { botiga_id: editant.botiga_id, tipus: editant.tipus, actiu: editant.actiu, dia_setmana: editant.dia_setmana, dia_mes: editant.dia_mes, data: editant.data, hora: editant.hora, destinataris: editant.destinataris }
    : { botiga_id: filtre.botiga ?? null, tipus: 'diari', actiu: true, dia_setmana: 0, dia_mes: 1, data: null, hora: '08:00', destinataris: [] };
  const [p, setP] = useState<NovaProgramacio>(inicial);
  const [correus, setCorreus] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enCurs, setEnCurs] = useState(false);
  useEffect(() => {
    const d = ref.current;
    if (editant && d && !d.open) { setP(inicial); setCorreus(inicial.destinataris.join(', ')); setError(null); d.showModal(); }
    if (!editant && d?.open) d.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editant]);
  const r = recurrencia(p.tipus);
  const propera = properaExecucio({ ...p, actiu: true });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const { correus: llista, dolents } = llegeixCorreus(correus);
    if (dolents.length) { setError(`Aquest correu no sembla vàlid: ${dolents[0]}`); return; }
    if (r === 'data' && !p.data) { setError('Tria el dia en què s’ha de generar.'); return; }
    const cos: NovaProgramacio = { ...p, destinataris: llista, dia_setmana: r === 'setmanal' ? p.dia_setmana ?? 0 : null, dia_mes: r === 'mensual' ? p.dia_mes ?? 1 : null, data: r === 'data' ? p.data : null };
    setEnCurs(true); setError(null);
    try {
      if (editant && editant !== 'nova') await informes.canviaProgramacio(editant.id, cos); else await informes.creaProgramacio(cos);
      enTanca(true);
    } catch (err) { setError((err as Error).message); } finally { setEnCurs(false); }
  };
  const canvia = <K extends keyof NovaProgramacio>(k: K, v: NovaProgramacio[K]) => setP((x) => ({ ...x, [k]: v }));
  return (
    <dialog ref={ref} className="dialeg" aria-labelledby="titol-prog" onClose={() => enTanca(false)}>
      <form className="formulari" onSubmit={submit} noValidate>
        <h2 id="titol-prog">{editant && editant !== 'nova' ? 'Edita la programació' : 'Nova programació'}</h2>
        <div className="dues">
          <label className="camp"><span>Informe</span>
            <select value={p.tipus} onChange={(e) => canvia('tipus', e.target.value as TipusInforme)}>{INFORMES.map((i) => <option key={i.tipus} value={i.tipus}>{i.nom}</option>)}</select>
          </label>
          <label className="camp"><span>Botiga</span>
            <select value={p.botiga_id ?? ''} onChange={(e) => canvia('botiga_id', e.target.value || null)}><option value="">Totes les botigues</option>{botigues.map((b) => <option key={b.id} value={b.id}>{b.nom}</option>)}</select>
          </label>
          {r === 'setmanal' && (
            <label className="camp"><span>Dia de la setmana</span>
              <select value={p.dia_setmana ?? 0} onChange={(e) => canvia('dia_setmana', Number(e.target.value))}>{DIES_SETMANA_LLARG.map((d, i) => <option key={d} value={i}>{d}</option>)}</select>
            </label>
          )}
          {r === 'mensual' && (
            <label className="camp"><span>Dia del mes</span>
              <select value={p.dia_mes ?? 1} onChange={(e) => canvia('dia_mes', Number(e.target.value))}>{Array.from({ length: 28 }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}</select>
              <small>Fins al 28, perquè tots els mesos el tinguin.</small>
            </label>
          )}
          {r === 'data' && <label className="camp"><span>Dia</span><input type="date" value={p.data ?? ''} onChange={(e) => canvia('data', e.target.value || null)} /></label>}
          <label className="camp"><span>Hora</span><input type="time" value={p.hora} step={900} onChange={(e) => canvia('hora', e.target.value)} /></label>
        </div>
        <p className="avis" style={{ margin: 0 }} aria-live="polite">
          {descriuProgramacio(p)}.<br /><b>Propera vegada:</b> {textPropera(propera)}{propera && r !== 'diari' ? ` (${diaLlarg(propera.toISOString())})` : ''}.
        </p>
        <label className="camp"><span>A qui s’envia</span>
          <textarea rows={2} value={correus} onChange={(e) => setCorreus(e.target.value)} placeholder="encarregada@marca.cat, producte@marca.cat" />
          <small>Separats per comes. Si ho deixes buit, només es guarda a «Lliurats».</small>
        </label>
        <label className="interruptor"><input type="checkbox" checked={p.actiu} onChange={(e) => canvia('actiu', e.target.checked)} />Activa</label>
        {error && <p className="missatge-error" role="alert">{error}</p>}
        <div className="fila" style={{ justifyContent: 'flex-end' }}>
          <button type="button" onClick={() => enTanca(false)}>Cancel·la</button>
          <button type="submit" className="boto-primari" disabled={enCurs}>{enCurs ? 'Desant…' : 'Desa'}</button>
        </div>
      </form>
    </dialog>
  );
}
