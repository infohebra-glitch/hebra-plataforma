/**
 * Connexions (F.4): Shopify, Square i CSV per URL. Els secrets només s'escriuen:
 * mai es tornen a ensenyar («Desat» + «Substitueix»).
 */
import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { integracions } from '../api/endpoints';
import type { AbastSync, Integracio, NovaIntegracio, Proveidor, RegistreSync, ResultatProvaIntegracio } from '../api/types';
import { useSessio } from '../context/Sessio';
import { diaCurt, enter, hora, plural } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Buit, Consulta, Esquelet } from './Estat';
import { faTemps } from '../lib/useCabines';

const PROVEIDORS: { p: Proveidor; nom: string; descripcio: string; secret: string; ajudaSecret: string }[] = [
  { p: 'shopify', nom: 'Shopify', descripcio: 'Botiga en línia o TPV de Shopify: catàleg, vendes (amb devolucions) i estoc d’una ubicació.', secret: 'Testimoni d’accés (shpat_…)', ajudaSecret: 'Crea una app personalitzada a Shopify amb permisos només de lectura: productes, comandes, inventari i ubicacions.' },
  { p: 'square', nom: 'Square', descripcio: 'TPV de Square: catàleg, vendes per ubicació i estoc.', secret: 'Testimoni d’accés', ajudaSecret: 'Al tauler de desenvolupadors de Square, a «Credentials». Només lectura.' },
  { p: 'csv_url', nom: 'CSV per URL', descripcio: 'Per a TPV que exporten un fitxer (Ágora, Revo, Lightspeed…): Hebra el descarrega cada cert temps.', secret: 'Capçalera d’autorització (opcional)', ajudaSecret: 'Si l’adreça demana clau, per exemple «Bearer abc123».' },
];
const ABAST: { a: AbastSync; nom: string }[] = [{ a: 'cataleg', nom: 'Catàleg' }, { a: 'vendes', nom: 'Vendes' }, { a: 'estoc', nom: 'Estoc' }];
const INTERVALS = [15, 30, 60, 120, 240, 1440];
const nomInterval = (m: number) => (m < 60 ? `Cada ${m} min` : m === 60 ? 'Cada hora' : m === 1440 ? 'Un cop al dia' : `Cada ${m / 60} h`);

export function Connexions() {
  const q = useApi((s) => integracions.llista(s), []);
  return (
    <div className="pila">
      {PROVEIDORS.map((def) => (
        <section key={def.p} className="panell proveidor" aria-labelledby={`prov-${def.p}`}>
          <div className="panell-capcalera">
            <div><h2 id={`prov-${def.p}`}>{def.nom}</h2><p className="muted" style={{ margin: '2px 0 0' }}>{def.descripcio}</p></div>
          </div>
          <Consulta q={q} esquelet={<Esquelet tipus="taula" files={2} />}>
            {(r) => <BlocProveidor def={def} llista={r.integracions.filter((i) => i.proveidor === def.p)} enCanvi={q.recarrega} />}
          </Consulta>
        </section>
      ))}
    </div>
  );
}

function BlocProveidor({ def, llista, enCanvi }: { def: (typeof PROVEIDORS)[number]; llista: Integracio[]; enCanvi: () => void }) {
  const [nova, setNova] = useState(false);
  return (
    <div className="pila" style={{ gap: 12 }}>
      {llista.map((i) => <TargetaIntegracio key={i.id} i={i} def={def} enCanvi={enCanvi} />)}
      {!llista.length && !nova && <p className="muted" style={{ margin: 0 }}>Encara no hi ha cap botiga connectada.</p>}
      {nova ? <FormIntegracio def={def} enTanca={(desat) => { setNova(false); if (desat) enCanvi(); }} />
        : <div><button type="button" onClick={() => setNova(true)}>Connecta {llista.length ? 'una altra botiga' : def.nom}</button></div>}
    </div>
  );
}

function EstatIntegracio({ i }: { i: Integracio }) {
  if (!i.actiu) return <span className="insignia insignia-mostra">Aturada</span>;
  if (i.estat === 'ok') return <span className="insignia insignia-bo">✓ Funciona</span>;
  if (i.estat === 'error') return <span className="insignia insignia-critic">✕ Error</span>;
  return <span className="insignia insignia-neutra">Encara no s’ha sincronitzat</span>;
}

function TargetaIntegracio({ i, def, enCanvi }: { i: Integracio; def: (typeof PROVEIDORS)[number]; enCanvi: () => void }) {
  const { botigues } = useSessio();
  const [editant, setEditant] = useState(false);
  const [registre, setRegistre] = useState<RegistreSync[] | null>(null);
  const [veureRegistre, setVeureRegistre] = useState(false);
  const [enCurs, setEnCurs] = useState(false);
  const [missatge, setMissatge] = useState<{ ok: boolean; text: string } | null>(null);
  const nomBotiga = i.botiga_id ? botigues.find((b) => b.id === i.botiga_id)?.nom ?? i.botiga_id : 'Tota la marca';
  const carregaRegistre = async () => { try { setRegistre((await integracions.registre(i.id)).registre); } catch { setRegistre([]); } };
  const sincronitza = async () => {
    setEnCurs(true); setMissatge(null);
    try {
      const { resum } = await integracions.sincronitza(i.id);
      setMissatge({ ok: true, text: `Fet: ${[resum.cataleg && plural(resum.cataleg, 'producte', 'productes'), resum.linies_venda && plural(resum.linies_venda, 'línia de venda', 'línies de venda'), resum.devolucions && plural(resum.devolucions, 'devolució', 'devolucions'), resum.estoc && plural(resum.estoc, 'nivell d’estoc', 'nivells d’estoc')].filter(Boolean).join(', ') || 'res de nou'}.` });
    } catch (e) { setMissatge({ ok: false, text: (e as Error).message }); }
    finally { setEnCurs(false); enCanvi(); if (veureRegistre) void carregaRegistre(); }
  };
  const commuta = async () => { try { await integracions.canvia(i.id, { actiu: !i.actiu }); enCanvi(); } catch (e) { setMissatge({ ok: false, text: (e as Error).message }); } };
  const esborra = async () => {
    if (!window.confirm(`Vols desconnectar ${def.nom} de ${nomBotiga}? Les dades ja importades es queden.`)) return;
    try { await integracions.esborra(i.id); enCanvi(); } catch (e) { setMissatge({ ok: false, text: (e as Error).message }); }
  };
  if (editant) return <FormIntegracio def={def} inicial={i} enTanca={(desat) => { setEditant(false); if (desat) enCanvi(); }} />;
  const ubicacio = (i.config.ubicacio_nom as string | undefined) ?? (i.config.domini as string | undefined);
  return (
    <article className={`targeta integracio ${i.estat}`} aria-label={`${def.nom} · ${nomBotiga}`}>
      <div className="targeta-cap">
        <div><h3>{nomBotiga}</h3>{ubicacio && <div className="petit muted">{ubicacio}{i.config.domini && i.config.ubicacio_nom ? ` · ${i.config.domini}` : ''}</div>}</div>
        <EstatIntegracio i={i} />
      </div>
      <ul className="metadades">
        <li><b>Porta:</b> {i.abast.map((a) => ABAST.find((x) => x.a === a)?.nom).join(', ') || '—'}</li>
        <li><b>Freqüència:</b> {nomInterval(i.interval_min).toLowerCase()}</li>
        <li><b>Darrera:</b> {i.darrera_sync ? `${diaCurt(i.darrera_sync)} a les ${hora(i.darrera_sync)} (${faTemps(i.darrera_sync)})` : 'mai'}</li>
        <li><b>Clau:</b> {i.te_secret ? 'desada ✓' : 'cap'}</li>
      </ul>
      {i.missatge && <p className={i.estat === 'error' ? 'avis-error' : 'petit muted'} style={{ margin: 0 }}>{i.missatge}</p>}
      <div role="status" aria-live="polite">{missatge && <p className={missatge.ok ? 'missatge-ok' : 'missatge-error'} style={{ margin: 0 }}>{missatge.text}</p>}</div>
      <div className="fila">
        <button type="button" className="boto-primari boto-petit" onClick={sincronitza} disabled={enCurs || !i.actiu}>{enCurs ? 'Sincronitzant…' : 'Sincronitza ara'}</button>
        <button type="button" className="boto-petit" onClick={() => setEditant(true)}>Edita</button>
        <button type="button" className="boto-petit" aria-expanded={veureRegistre} onClick={() => { setVeureRegistre(!veureRegistre); if (!registre) void carregaRegistre(); }}>Registre</button>
        <label className="interruptor petit"><input type="checkbox" checked={i.actiu} onChange={commuta} />Activa</label>
        <span style={{ flex: 1 }} />
        <button type="button" className="boto-petit boto-fantasma" onClick={esborra}>Desconnecta</button>
      </div>
      {veureRegistre && (
        <div className="registre">
          {!registre ? <Esquelet tipus="taula" files={3} /> : registre.length ? (
            <div className="taula-wrap"><table>
              <caption className="sr-only">Darreres sincronitzacions</caption>
              <thead><tr><th scope="col">Quan</th><th scope="col">Estat</th><th scope="col">Què ha portat</th></tr></thead>
              <tbody>{registre.map((r, k) => (
                <tr key={k}>
                  <td className="num">{diaCurt(r.inici)} {hora(r.inici)}</td>
                  <td>{r.estat === 'ok' ? <span className="insignia insignia-bo">✓ Bé</span> : <span className="insignia insignia-critic">✕ Error</span>}</td>
                  <td className="petit">{r.error ?? (r.resum ? Object.entries(r.resum).filter(([, n]) => n).map(([k2, n]) => `${enter(n as number)} ${({ cataleg: 'productes', linies_venda: 'línies de venda', devolucions: 'devolucions', estoc: 'nivells d’estoc' } as Record<string, string>)[k2] ?? k2}`).join(', ') || 'res de nou' : '—')}</td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <Buit titol="Encara cap sincronització" />}
        </div>
      )}
    </article>
  );
}

function CampSecret({ etiqueta, ajuda, desat, valor, setValor, obligatori }: { etiqueta: string; ajuda: string; desat: boolean; valor: string | null; setValor: (v: string | null) => void; obligatori?: boolean }) {
  const id = useId();
  if (desat && valor === null) {
    return (
      <div className="camp">
        <span>{etiqueta}</span>
        <div className="fila"><span className="insignia insignia-bo">✓ Desat</span><span className="petit muted">Per seguretat no es torna a ensenyar.</span><button type="button" className="boto-petit" onClick={() => setValor('')}>Substitueix</button></div>
      </div>
    );
  }
  return (
    <label className="camp" htmlFor={id}>
      <span>{etiqueta}{obligatori && !desat ? '' : ' (opcional)'}</span>
      <div className="fila">
        <input id={id} type="password" autoComplete="off" spellCheck={false} value={valor ?? ''} onChange={(e) => setValor(e.target.value)} style={{ flex: '1 1 220px' }} />
        {desat && <button type="button" className="boto-petit boto-fantasma" onClick={() => setValor(null)}>Mantén el desat</button>}
      </div>
      <small>{ajuda} Es desa xifrat i no es pot tornar a llegir.</small>
    </label>
  );
}

function FormIntegracio({ def, inicial, enTanca }: { def: (typeof PROVEIDORS)[number]; inicial?: Integracio; enTanca: (desat: boolean) => void }) {
  const { botigues } = useSessio();
  const [botiga, setBotiga] = useState<string>(inicial ? inicial.botiga_id ?? '' : botigues[0]?.id ?? '');
  const [config, setConfig] = useState<Record<string, unknown>>(inicial?.config ?? (def.p === 'shopify' ? { opcio_talla: 'Talla', opcio_color: 'Color', incloure_en_linia: false } : {}));
  const [secret, setSecret] = useState<string | null>(inicial?.te_secret ? null : '');
  const [abast, setAbast] = useState<AbastSync[]>(inicial?.abast ?? (def.p === 'csv_url' ? ['vendes', 'estoc'] : ['cataleg', 'vendes', 'estoc']));
  const [interval, setIntervalMin] = useState(inicial?.interval_min ?? 60);
  const [prova, setProva] = useState<ResultatProvaIntegracio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enCurs, setEnCurs] = useState<'prova' | 'desa' | null>(null);
  const cfg = (k: string) => String(config[k] ?? '');
  const posa = (k: string, v: unknown) => { setConfig((c) => ({ ...c, [k]: v })); setProva(null); };
  const ubicacions = prova?.detall.ubicacions ?? [];

  const fesProva = async () => {
    setEnCurs('prova'); setError(null); setProva(null);
    try {
      const r = await integracions.prova({ proveidor: def.p, config, secret: secret || null, id: inicial?.id });
      setProva(r);
      const u = r.detall.ubicacions;
      if (u?.length === 1 && !config.ubicacio_id) setConfig((c) => ({ ...c, ubicacio_id: u[0].id, ubicacio_nom: u[0].nom }));
    } catch (e) { setError((e as Error).message); } finally { setEnCurs(null); }
  };
  const desa = async (e: FormEvent) => {
    e.preventDefault();
    if (!abast.length) { setError('Tria què vols portar: catàleg, vendes o estoc.'); return; }
    if (def.p !== 'csv_url' && !inicial?.te_secret && !secret) { setError('Falta el testimoni d’accés.'); return; }
    if (def.p !== 'csv_url' && !config.ubicacio_id) { setError('Prova la connexió i tria la ubicació de la botiga.'); return; }
    setEnCurs('desa'); setError(null);
    try {
      if (inicial) await integracions.canvia(inicial.id, { config, abast, interval_min: interval, botiga_id: botiga || null, ...(secret ? { secret } : {}) });
      else await integracions.crea({ botiga_id: botiga || null, proveidor: def.p, config, secret: secret || null, abast, interval_min: interval } satisfies NovaIntegracio);
      enTanca(true);
    } catch (err) { setError((err as Error).message); } finally { setEnCurs(null); }
  };
  const camp = (k: string, etiqueta: string, ajuda: ReactNode, placeholder?: string) => (
    <label className="camp"><span>{etiqueta}</span><input value={cfg(k)} onChange={(e) => posa(k, e.target.value.trim())} placeholder={placeholder} spellCheck={false} /><small>{ajuda}</small></label>
  );
  return (
    <form className="targeta form-integracio formulari" onSubmit={desa} noValidate aria-label={`${inicial ? 'Edita' : 'Connecta'} ${def.nom}`}>
      <h3>{inicial ? `Edita ${def.nom}` : `Connecta ${def.nom}`}</h3>
      <label className="camp"><span>Botiga de Hebra</span>
        <select value={botiga} onChange={(e) => setBotiga(e.target.value)}>
          {botigues.map((b) => <option key={b.id} value={b.id}>{b.nom}</option>)}
          <option value="">Tota la marca</option>
        </select>
      </label>
      {def.p === 'shopify' && camp('domini', 'Domini de Shopify', 'El que acaba en .myshopify.com (no el domini propi).', 'nom-botiga.myshopify.com')}
      {def.p === 'csv_url' && (
        <>
          {camp('url_vendes', 'URL de les vendes', 'Columnes: data_hora, botiga, gtin, quantitat (les devolucions, en negatiu).', 'https://…/vendes.csv')}
          {camp('url_estoc', 'URL de l’estoc', 'Columnes: botiga, gtin, unitats.', 'https://…/estoc.csv')}
          {camp('url_cataleg', 'URL del catàleg', 'Columnes: gtin, model, nom, categoria, color, talla, preu.', 'https://…/cataleg.csv')}
        </>
      )}
      <CampSecret etiqueta={def.secret} ajuda={def.ajudaSecret} desat={!!inicial?.te_secret} valor={secret} setValor={setSecret} obligatori={def.p !== 'csv_url'} />
      <div className="fila">
        <button type="button" onClick={fesProva} disabled={enCurs !== null}>{enCurs === 'prova' ? 'Provant…' : 'Prova la connexió'}</button>
        <span role="status" aria-live="polite" className="petit">{prova?.ok && <span className="missatge-ok">✓ Connecta{prova.detall.botiga ? ` amb «${prova.detall.botiga}»` : ''}.</span>}</span>
      </div>
      {prova?.ok && Array.isArray(prova.detall.fitxers) && (
        <ul className="petit" style={{ margin: 0, paddingLeft: 18 }}>
          {(prova.detall.fitxers as { url: string; files: number }[]).map((f) => <li key={f.url}>{f.url.split('/').pop()}: {plural(f.files, 'fila', 'files')}</li>)}
        </ul>
      )}
      {(ubicacions.length > 0 || !!config.ubicacio_id) && def.p !== 'csv_url' && (
        <fieldset className="sense-vora">
          <legend className="etiqueta-mini">Ubicació que correspon a aquesta botiga</legend>
          {ubicacions.length ? (
            <div className="pila" style={{ gap: 4 }}>
              {ubicacions.map((u) => (
                <label key={u.id} className="interruptor"><input type="radio" name={`ubicacio-${def.p}`} checked={config.ubicacio_id === u.id} onChange={() => setConfig((c) => ({ ...c, ubicacio_id: u.id, ubicacio_nom: u.nom }))} />{u.nom}</label>
              ))}
            </div>
          ) : <p className="petit" style={{ margin: 0 }}>{String(config.ubicacio_nom ?? config.ubicacio_id)} · <span className="muted">prova la connexió per canviar-la</span></p>}
        </fieldset>
      )}
      <fieldset className="sense-vora">
        <legend className="etiqueta-mini">Què es porta</legend>
        <div className="xips-tria">
          {ABAST.map((x) => {
            const on = abast.includes(x.a);
            return <label key={x.a} className={on ? 'on' : undefined}><input type="checkbox" checked={on} onChange={(e) => setAbast(e.target.checked ? [...abast, x.a] : abast.filter((y) => y !== x.a))} />{x.nom}</label>;
          })}
        </div>
        {abast.includes('vendes') && <small className="muted">Les vendes es tornen a llegir des de 2 dies abans de la darrera sincronització, per agafar les devolucions.</small>}
      </fieldset>
      <div className="dues">
        <label className="camp"><span>Cada quan</span><select value={interval} onChange={(e) => setIntervalMin(Number(e.target.value))}>{INTERVALS.map((m) => <option key={m} value={m}>{nomInterval(m)}</option>)}</select></label>
        {def.p === 'shopify' && (
          <label className="interruptor" style={{ alignSelf: 'end' }}><input type="checkbox" checked={!!config.incloure_en_linia} onChange={(e) => posa('incloure_en_linia', e.target.checked)} />Inclou també les vendes en línia</label>
        )}
      </div>
      {def.p === 'shopify' && (
        <details className="veure-taula">
          <summary>Opcions avançades</summary>
          <div className="dues" style={{ marginTop: 8 }}>
            {camp('opcio_talla', 'Nom de l’opció de talla', 'Com es diu a Shopify: «Talla», «Size»…')}
            {camp('opcio_color', 'Nom de l’opció de color', 'Per defecte, «Color».')}
          </div>
        </details>
      )}
      {error && <p className="missatge-error" role="alert">{error}</p>}
      <div className="fila" style={{ justifyContent: 'flex-end' }}>
        <button type="button" onClick={() => enTanca(false)}>Cancel·la</button>
        <button type="submit" className="boto-primari" disabled={enCurs !== null}>{enCurs === 'desa' ? 'Desant…' : inicial ? 'Desa els canvis' : 'Connecta'}</button>
      </div>
    </form>
  );
}
