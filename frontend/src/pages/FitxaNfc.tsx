/**
 * Fitxa NFC (A): què veu el client quan toca l'etiqueta. Configuració general i
 * per botiga, contingut per model i idioma, i una vista prèvia com un mòbil al costat.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { analitica, fitxa } from '../api/endpoints';
import type { ConfigFitxa, ConfigFitxaParcial, ContingutModel, DetallModelFitxa, ModelFitxa, MostraEstoc, MotiuFitxa, SeccioFitxa } from '../api/types';
import { Consulta, ErrorEstat, Esquelet } from '../components/Estat';
import { FitxaPrevia } from '../components/FitxaPrevia';
import { Icona } from '../components/Icones';
import { TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { idioma as nomIdioma } from '../lib/etiquetes';
import { GRUPS, IDIOMES_FITXA, MAX_LOGO, MOTIUS_FITXA, SECCIONS_FITXA, colorValid, combina, contrast, mou, nomSeccioFitxa, validaLogo } from '../lib/fitxa';
import { esMock } from '../lib/mode';
import { useApi } from '../lib/useApi';

type Grup = (typeof GRUPS)[number];
const NOMS_GRUP: Record<Grup, string> = { seccions: 'Seccions', accions: 'Botons del client', idiomes: 'Idiomes', textos: 'Textos de la marca', 'aparença': 'Aparença', motius: 'Motius de «Per què no»' };
const igual = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export function FitxaNfc() {
  const { botigues } = useSessio();
  const { filtre } = useFiltre();
  const [ambit, setAmbit] = useState<string>(filtre.botiga ?? '');
  const [pestanya, setPestanya] = useState<'config' | 'contingut'>('config');
  const qc = useApi((s) => fitxa.config(ambit || undefined, s), [ambit]);
  const qm = useApi((s) => fitxa.models(s), []);
  const [model, setModel] = useState('');
  const [idiomaPrevia, setIdiomaPrevia] = useState('ca');
  const [versio, setVersio] = useState(0);
  // Esborranys (perquè la vista prèvia de la demo els ensenyi sense desar)
  const [general, setGeneral] = useState<ConfigFitxa | null>(null);
  const [parcial, setParcial] = useState<ConfigFitxaParcial>({});
  const [contingut, setContingut] = useState<{ model: string; idioma: string; c: ContingutModel } | null>(null);

  useEffect(() => { if (qc.dades) { setGeneral(structuredClone(qc.dades.general)); setParcial(structuredClone(qc.dades.botiga ?? {})); } }, [qc.dades]);
  useEffect(() => { if (!model && qm.dades?.models.length) setModel(qm.dades.models[0].model); }, [qm.dades, model]);
  const efectiva = useMemo(() => (general ? (ambit ? combina(general, parcial) : general) : null), [general, parcial, ambit]);
  useEffect(() => { if (efectiva && !efectiva.idiomes.includes(idiomaPrevia)) setIdiomaPrevia(efectiva.idiomes[0] ?? 'ca'); }, [efectiva, idiomaPrevia]);

  const nomBotiga = ambit ? botigues.find((b) => b.id === ambit)?.nom ?? ambit : '';
  return (
    <>
      <TitolPagina titol="Fitxa NFC" senseperiode>
        Què veu el client quan toca l’etiqueta de la peça a la cabina. Tria què s’ensenya, en quin ordre, en quins idiomes i amb quins textos.
      </TitolPagina>
      <Enllacos />
      <div className="barra-eines" style={{ marginTop: 16 }}>
        <label className="camp-linia"><span>Configuració de</span>
          <select value={ambit} onChange={(e) => setAmbit(e.target.value)}>
            <option value="">Totes les botigues (general)</option>
            {botigues.map((b) => <option key={b.id} value={b.id}>{b.nom}</option>)}
          </select>
        </label>
        <div className="pestanyes" role="tablist" aria-label="Fitxa NFC" style={{ margin: 0, border: 0 }}>
          <button type="button" role="tab" aria-selected={pestanya === 'config'} className={`pestanya${pestanya === 'config' ? ' activa' : ''}`} onClick={() => setPestanya('config')}>Configuració</button>
          <button type="button" role="tab" aria-selected={pestanya === 'contingut'} className={`pestanya${pestanya === 'contingut' ? ' activa' : ''}`} onClick={() => setPestanya('contingut')}>Contingut per model</button>
        </div>
      </div>
      <div className="fitxa-disseny">
        <div className="fitxa-editor">
          {pestanya === 'config' ? (
            qc.error && !qc.dades ? <ErrorEstat error={qc.error} reintenta={qc.recarrega} /> :
            !general || !efectiva || !qc.dades ? <Esquelet tipus="taula" files={8} /> : (
              <EditorConfig ambit={ambit} nomBotiga={nomBotiga} general={general} parcial={parcial} efectiva={efectiva}
                desat={{ general: qc.dades.general, botiga: qc.dades.botiga ?? {} }}
                setGeneral={setGeneral} setParcial={setParcial}
                enDesat={(r) => { setGeneral(structuredClone(r.general)); setParcial(structuredClone(r.botiga ?? {})); setVersio((v) => v + 1); }} />
            )
          ) : (
            <Consulta q={qm} esquelet={<Esquelet tipus="taula" files={6} />}>
              {(r) => <EditorContingut models={r.models} model={model} setModel={setModel} idiomes={general?.idiomes ?? ['ca']}
                idioma={idiomaPrevia} setIdioma={setIdiomaPrevia} enEsborrany={setContingut} enDesat={() => { qm.recarrega(); setVersio((v) => v + 1); }} />}
            </Consulta>
          )}
        </div>
        <aside className="fitxa-previa" aria-label="Vista prèvia de la fitxa">
          {efectiva && qm.dades && (
            <Previa config={efectiva} models={qm.dades.models} model={model} setModel={setModel} idioma={idiomaPrevia} setIdioma={setIdiomaPrevia}
              botiga={ambit || undefined} versio={versio} esborrany={contingut} />
          )}
        </aside>
      </div>
    </>
  );
}

function Enllacos() {
  return (
    <section className="panell enllacos-fitxa" aria-labelledby="t-com">
      <h2 id="t-com" style={{ fontSize: 17 }}>Com es connecta amb la resta</h2>
      <ol>
        <li><b>El client</b> toca l’etiqueta i veu aquesta fitxa al mòbil, sense cap app ni galeta.</li>
        <li><b>«Demana una altra talla»</b> i <b>«Vull que m’atenguin»</b> arriben a l’instant a la <Link to="/dependent">web del dependent</Link>, amb el número de cabina. Les d’ajuda porten el distintiu «Assistència».</li>
        <li><b>«Per què no te l’emportes?»</b> alimenta <Link to="/per-que">Per què no compren</Link>; les seccions que obren surten a l’ús de la fitxa.</li>
        <li><b>L’origen</b> només s’ensenya els dies que la <Link to="/origen">prova d’origen</Link> ho permet, encara que aquí estigui visible.</li>
      </ol>
    </section>
  );
}

// ── Configuració ─────────────────────────────────────────────────────────

function EditorConfig({ ambit, nomBotiga, general, parcial, efectiva, desat, setGeneral, setParcial, enDesat }: {
  ambit: string; nomBotiga: string; general: ConfigFitxa; parcial: ConfigFitxaParcial; efectiva: ConfigFitxa;
  desat: { general: ConfigFitxa; botiga: ConfigFitxaParcial };
  setGeneral: (c: ConfigFitxa) => void; setParcial: (p: ConfigFitxaParcial) => void; enDesat: (r: { general: ConfigFitxa; botiga: ConfigFitxaParcial | null }) => void;
}) {
  const [missatge, setMissatge] = useState<{ ok: boolean; text: string } | null>(null);
  const [desant, setDesant] = useState(false);
  const brut = ambit ? !igual(parcial, desat.botiga) : !igual(general, desat.general);
  const edita = <G extends Grup>(g: G, v: ConfigFitxa[G]) => {
    setMissatge(null);
    if (ambit) setParcial({ ...parcial, [g]: v });
    else setGeneral({ ...general, [g]: v });
  };
  const personalitzat = (g: Grup) => !ambit || parcial[g] !== undefined;
  const commuta = (g: Grup) => {
    const p = { ...parcial };
    if (p[g] !== undefined) delete p[g]; else (p as Record<string, unknown>)[g] = structuredClone(efectiva[g]);
    setParcial(p);
  };
  const desa = async () => {
    const ap = efectiva['aparença'];
    if (!colorValid(ap.color_principal)) { setMissatge({ ok: false, text: 'El color ha de ser del tipus #214F46.' }); return; }
    if (!efectiva.idiomes.length) { setMissatge({ ok: false, text: 'Tria com a mínim un idioma.' }); return; }
    setDesant(true); setMissatge(null);
    try {
      const r = await fitxa.desaConfig(ambit ? parcial : general, ambit || undefined);
      enDesat(r);
      setMissatge({ ok: true, text: ambit ? `Desat per a ${nomBotiga}. Els clients ja ho veuen així.` : 'Desat. Els clients de totes les botigues ja ho veuen així.' });
    } catch (e) { setMissatge({ ok: false, text: (e as Error).message }); } finally { setDesant(false); }
  };
  const desfes = () => { setGeneral(structuredClone(desat.general)); setParcial(structuredClone(desat.botiga)); setMissatge(null); };
  const c = efectiva;
  const targeta = (g: Grup, ajuda: ReactNode, cos: ReactNode) => (
    <section className="targeta grup-fitxa" aria-labelledby={`g-${g}`}>
      <div className="targeta-cap">
        <h3 id={`g-${g}`}>{NOMS_GRUP[g]}</h3>
        {ambit && (
          <label className="interruptor petit"><input type="checkbox" checked={personalitzat(g)} onChange={() => commuta(g)} />Diferent a {nomBotiga.split(' · ')[0]}</label>
        )}
      </div>
      <p className="petit muted" style={{ margin: 0 }}>{ambit && !personalitzat(g) ? 'Fa servir la configuració general. Marca la casella per canviar-ho només en aquesta botiga.' : ajuda}</p>
      <fieldset disabled={!personalitzat(g)} className="sense-vora">
        <legend className="sr-only">{NOMS_GRUP[g]}</legend>
        {cos}
      </fieldset>
    </section>
  );

  return (
    <div className="pila">
      {ambit && <p className="avis" style={{ margin: 0 }}>Estàs editant <b>{nomBotiga}</b>. Només canvien els apartats marcats com a «Diferent»; la resta segueix la configuració general.</p>}

      {targeta('seccions', 'L’ordre de la llista és l’ordre a la fitxa. Les ocultes no surten.', (
        <ol className="llista-ordenable">
          {c.seccions.ordre.map((s, i) => {
            const def = SECCIONS_FITXA.find((x) => x.clau === s);
            const visible = c.seccions.visibles[s];
            return (
              <li key={s} className={visible ? undefined : 'oculta'}>
                <span className="ordre-num" aria-hidden="true">{i + 1}</span>
                <span className="ordre-text"><b>{nomSeccioFitxa(s)}</b><small>{def?.ajuda}</small></span>
                <label className="interruptor petit"><input type="checkbox" checked={visible} onChange={(e) => edita('seccions', { ...c.seccions, visibles: { ...c.seccions.visibles, [s]: e.target.checked } })} />{visible ? 'Visible' : 'Oculta'}</label>
                <span className="fila" style={{ gap: 4 }}>
                  <button type="button" className="boto-icona" disabled={i === 0} onClick={() => edita('seccions', { ...c.seccions, ordre: mou(c.seccions.ordre, i, -1) as SeccioFitxa[] })} aria-label={`Puja ${nomSeccioFitxa(s)}`}><Icona nom="amunt" mida={16} /></button>
                  <button type="button" className="boto-icona" disabled={i === c.seccions.ordre.length - 1} onClick={() => edita('seccions', { ...c.seccions, ordre: mou(c.seccions.ordre, i, 1) as SeccioFitxa[] })} aria-label={`Baixa ${nomSeccioFitxa(s)}`}><Icona nom="avall" mida={16} /></button>
                </span>
              </li>
            );
          })}
        </ol>
      ))}

      {targeta('accions', 'Els botons que pot prémer el client i on arriben.', (
        <div className="pila" style={{ gap: 10 }}>
          <Opcio checked={c.accions.demana_talla} onChange={(v) => edita('accions', { ...c.accions, demana_talla: v })} titol="«Demana una altra talla»" ajuda="Arriba a la web del dependent amb la talla i la cabina. Si no n’hi ha, li diu en quina altra botiga n’hi ha." />
          <Opcio checked={c.accions.demana_assistencia} onChange={(v) => edita('accions', { ...c.accions, demana_assistencia: v })} titol="«Vull que m’atenguin»" ajuda="Arriba a la web del dependent amb el distintiu «Assistència»: algú va a la cabina." />
          <Opcio checked={c.accions.per_que_no} onChange={(v) => edita('accions', { ...c.accions, per_que_no: v })} titol="«Per què no te l’emportes?»" ajuda="Respostes anònimes que surten a «Per què no compren»." />
          <fieldset className="sense-vora">
            <legend className="etiqueta-mini">Estoc de les altres talles</legend>
            <div className="segmentat">
              {([['no', 'No l’ensenyis'], ['disponibilitat', 'Hi és / no hi és'], ['unitats', 'Unitats exactes']] as [MostraEstoc, string][]).map(([v, n]) => (
                <label key={v}><input type="radio" name="mostra_estoc" checked={c.accions.mostra_estoc === v} onChange={() => edita('accions', { ...c.accions, mostra_estoc: v })} />{n}</label>
              ))}
            </div>
          </fieldset>
        </div>
      ))}

      {targeta('idiomes', 'Els idiomes que s’ofereixen. El primer és el que surt si el mòbil del client no en demana cap altre.', (
        <EditorIdiomes idiomes={c.idiomes} onChange={(v) => edita('idiomes', v)} />
      ))}

      {targeta('textos', 'Una benvinguda a dalt i un peu a baix, en cada idioma. Si un idioma no en té, no surt res.', (
        <EditorTextos textos={c.textos} idiomes={c.idiomes} onChange={(v) => edita('textos', v)} />
      ))}

      {targeta('aparença', 'El nom, el color dels botons i el logo de la marca.', (
        <EditorAparenca ap={c['aparença']} onChange={(v) => edita('aparença', v)} />
      ))}

      {targeta('motius', 'Les respostes que pot triar el client. Com menys n’hi ha, més en contesten.', (
        <div className="xips-tria">
          {MOTIUS_FITXA.map((m) => {
            const on = c.motius.includes(m.clau);
            return (
              <label key={m.clau} className={on ? 'on' : undefined}>
                <input type="checkbox" checked={on} onChange={(e) => edita('motius', e.target.checked ? MOTIUS_FITXA.map((x) => x.clau).filter((k) => k === m.clau || c.motius.includes(k)) as MotiuFitxa[] : c.motius.filter((k) => k !== m.clau))} />{m.nom}
              </label>
            );
          })}
        </div>
      ))}

      <div className={`barra-desa${brut ? ' bruta' : ''}`} role="region" aria-label="Desar els canvis">
        <span role="status" aria-live="polite" className="petit">
          {missatge ? <span className={missatge.ok ? 'missatge-ok' : 'missatge-error'}>{missatge.text}</span> : brut ? 'Hi ha canvis sense desar.' : 'Tot desat.'}
        </span>
        <span className="fila">
          <button type="button" onClick={desfes} disabled={!brut || desant}>Desfés</button>
          <button type="button" className="boto-primari" onClick={desa} disabled={!brut || desant}>{desant ? 'Desant…' : 'Desa'}</button>
        </span>
      </div>
    </div>
  );
}

function Opcio({ checked, onChange, titol, ajuda }: { checked: boolean; onChange: (v: boolean) => void; titol: string; ajuda: string }) {
  return (
    <label className="opcio">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span><b>{titol}</b><small>{ajuda}</small></span>
    </label>
  );
}

function EditorIdiomes({ idiomes, onChange }: { idiomes: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="pila" style={{ gap: 10 }}>
      <div className="xips-tria">
        {IDIOMES_FITXA.map((i) => {
          const on = idiomes.includes(i);
          return <label key={i} className={on ? 'on' : undefined}><input type="checkbox" checked={on} disabled={on && idiomes.length === 1} onChange={(e) => onChange(e.target.checked ? [...idiomes, i] : idiomes.filter((x) => x !== i))} />{nomIdioma(i)}</label>;
        })}
      </div>
      <label className="camp-linia"><span>Per defecte</span>
        <select value={idiomes[0]} onChange={(e) => onChange([e.target.value, ...idiomes.filter((x) => x !== e.target.value)])}>
          {idiomes.map((i) => <option key={i} value={i}>{nomIdioma(i)}</option>)}
        </select>
      </label>
    </div>
  );
}

function EditorTextos({ textos, idiomes, onChange }: { textos: ConfigFitxa['textos']; idiomes: string[]; onChange: (v: ConfigFitxa['textos']) => void }) {
  const [i, setI] = useState(idiomes[0]);
  const actiu = idiomes.includes(i) ? i : idiomes[0];
  const posa = (k: 'benvinguda' | 'peu', v: string) => onChange({ ...textos, [k]: { ...(textos[k] ?? {}), [actiu]: v } });
  return (
    <div className="pila" style={{ gap: 10 }}>
      <SelectorIdioma idiomes={idiomes} actiu={actiu} setActiu={setI} amb={(x) => !!(textos.benvinguda?.[x] || textos.peu?.[x])} />
      <label className="camp"><span>Benvinguda ({nomIdioma(actiu)})</span><textarea rows={2} maxLength={280} value={textos.benvinguda?.[actiu] ?? ''} onChange={(e) => posa('benvinguda', e.target.value)} placeholder="Gràcies per provar-te una peça nostra." /></label>
      <label className="camp"><span>Peu ({nomIdioma(actiu)})</span><input maxLength={160} value={textos.peu?.[actiu] ?? ''} onChange={(e) => posa('peu', e.target.value)} placeholder="Fet amb cura a…" /></label>
    </div>
  );
}

function SelectorIdioma({ idiomes, actiu, setActiu, amb }: { idiomes: string[]; actiu: string; setActiu: (i: string) => void; amb: (i: string) => boolean }) {
  return (
    <div className="segmentat" role="group" aria-label="Idioma que edites">
      {idiomes.map((x) => (
        <button key={x} type="button" aria-pressed={x === actiu} className={x === actiu ? 'actiu' : undefined} onClick={() => setActiu(x)}>
          {x.toUpperCase()}{amb(x) ? <span aria-label=" (amb text)"> ●</span> : null}
        </button>
      ))}
    </div>
  );
}

function EditorAparenca({ ap, onChange }: { ap: ConfigFitxa['aparença']; onChange: (v: ConfigFitxa['aparença']) => void }) {
  const [hex, setHex] = useState(ap.color_principal);
  const [errorLogo, setErrorLogo] = useState<string | null>(null);
  const fitxer = useRef<HTMLInputElement>(null);
  useEffect(() => setHex(ap.color_principal), [ap.color_principal]);
  const valid = colorValid(hex);
  const ratio = valid ? contrast(hex, '#FFFFFF') : null;
  const llegeix = (f: File | undefined) => {
    setErrorLogo(null);
    if (!f) return;
    const e = validaLogo(f);
    if (e) { setErrorLogo(e); if (fitxer.current) fitxer.current.value = ''; return; }
    const r = new FileReader();
    r.onload = () => {
      const url = String(r.result);
      if (url.length * 0.75 > MAX_LOGO) { setErrorLogo('El logo no pot passar de 100 KB.'); return; }
      onChange({ ...ap, logo_data_url: url });
    };
    r.onerror = () => setErrorLogo('No s’ha pogut llegir el fitxer.');
    r.readAsDataURL(f);
  };
  return (
    <div className="pila" style={{ gap: 12 }}>
      <label className="camp"><span>Nom de la marca</span><input value={ap.nom_marca} maxLength={40} onChange={(e) => onChange({ ...ap, nom_marca: e.target.value })} /></label>
      <div className="camp">
        <label htmlFor="color-text">Color principal</label>
        <div className="fila">
          <input type="color" aria-label="Tria el color" value={valid ? hex : '#214F46'} onChange={(e) => { setHex(e.target.value.toUpperCase()); onChange({ ...ap, color_principal: e.target.value.toUpperCase() }); }} style={{ width: 52, padding: 2 }} />
          <input id="color-text" value={hex} maxLength={7} style={{ width: 110, fontFamily: 'var(--mono)' }} aria-invalid={!valid} aria-describedby="ajuda-color"
            onChange={(e) => { const v = e.target.value.trim(); setHex(v); if (colorValid(v)) onChange({ ...ap, color_principal: v.toUpperCase() }); }} />
          <span className="mostra-color" style={{ background: valid ? hex : 'transparent' }} aria-hidden="true">Aa</span>
        </div>
        <small id="ajuda-color">{!valid ? <span className="missatge-error">Escriu-lo com #214F46.</span> : ratio !== null && ratio < 4.5 ? <span className="missatge-error">Poc contrast amb el blanc ({ratio.toFixed(1)}:1): el text dels botons serà fosc perquè es llegeixi.</span> : `Contrast amb el blanc: ${ratio?.toFixed(1)}:1 (bé).`}</small>
      </div>
      <div className="camp">
        <label htmlFor="logo">Logo (PNG o SVG, com a màxim 100 KB)</label>
        <div className="fila">
          {ap.logo_data_url ? <img src={ap.logo_data_url} alt="Logo actual" className="logo-mostra" /> : <span className="muted petit">Sense logo: surt el nom de la marca.</span>}
          <input id="logo" ref={fitxer} type="file" accept="image/png,image/svg+xml" onChange={(e) => llegeix(e.target.files?.[0])} aria-describedby="error-logo" />
          {ap.logo_data_url && <button type="button" className="boto-petit" onClick={() => { onChange({ ...ap, logo_data_url: null }); if (fitxer.current) fitxer.current.value = ''; }}>Treu el logo</button>}
        </div>
        <small id="error-logo" role={errorLogo ? 'alert' : undefined}>{errorLogo && <span className="missatge-error">{errorLogo}</span>}</small>
      </div>
    </div>
  );
}

// ── Contingut per model ──────────────────────────────────────────────────

function EditorContingut({ models, model, setModel, idiomes, idioma, setIdioma, enEsborrany, enDesat }: {
  models: ModelFitxa[]; model: string; setModel: (m: string) => void; idiomes: string[]; idioma: string; setIdioma: (i: string) => void;
  enEsborrany: (c: { model: string; idioma: string; c: ContingutModel } | null) => void; enDesat: () => void;
}) {
  const q = useApi((s) => (model ? fitxa.model(model, s) : Promise.resolve(null)), [model]);
  return (
    <div className="pila">
      <div className="barra-eines">
        <label className="camp-linia"><span>Model</span>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {models.map((m) => <option key={m.model} value={m.model}>{m.nom} · {m.idiomes_amb_contingut.length ? m.idiomes_amb_contingut.map((i) => i.toUpperCase()).join(' ') : 'sense textos propis'}</option>)}
          </select>
        </label>
      </div>
      <Consulta q={q} esquelet={<Esquelet tipus="taula" files={6} />}>
        {(d) => d && <FormContingut key={`${d.model}`} d={d} models={models} idiomes={[...new Set([...idiomes, ...Object.keys(d.contingut)])]} idioma={idioma} setIdioma={setIdioma} enEsborrany={enEsborrany} enDesat={() => { q.recarrega(); enDesat(); }} />}
      </Consulta>
    </div>
  );
}

const buit = (c: ContingutModel) => Object.fromEntries(Object.entries(c).filter(([, v]) => (Array.isArray(v) ? v.length : v))) as ContingutModel;

function FormContingut({ d, models, idiomes, idioma, setIdioma, enEsborrany, enDesat }: {
  d: DetallModelFitxa; models: ModelFitxa[]; idiomes: string[]; idioma: string; setIdioma: (i: string) => void;
  enEsborrany: (c: { model: string; idioma: string; c: ContingutModel } | null) => void; enDesat: () => void;
}) {
  const actiu = idiomes.includes(idioma) ? idioma : idiomes[0];
  const desat = d.contingut[actiu] ?? {};
  const [c, setC] = useState<ContingutModel>(desat);
  const [missatge, setMissatge] = useState<{ ok: boolean; text: string } | null>(null);
  const [desant, setDesant] = useState(false);
  useEffect(() => { setC(d.contingut[actiu] ?? {}); setMissatge(null); }, [actiu, d]);
  useEffect(() => { enEsborrany({ model: d.model, idioma: actiu, c }); }, [c, actiu, d.model, enEsborrany]);
  useEffect(() => () => enEsborrany(null), [enEsborrany]);
  const brut = !igual(buit(c), buit(desat));
  const o = d.origen ?? {};
  const placeholder = (k: string) => (typeof o[k] === 'string' ? `Si ho deixes buit: «${String(o[k]).slice(0, 80)}»` : 'Opcional');
  const posa = <K extends keyof ContingutModel>(k: K, v: ContingutModel[K]) => { setC((x) => ({ ...x, [k]: v })); setMissatge(null); };
  const desa = async () => {
    setDesant(true); setMissatge(null);
    try { await fitxa.desaContingut(d.model, actiu, buit(c)); setMissatge({ ok: true, text: `Desat en ${nomIdioma(actiu).toLowerCase()}.` }); enDesat(); }
    catch (e) { setMissatge({ ok: false, text: (e as Error).message }); } finally { setDesant(false); }
  };
  const faq = c.faq ?? [];
  return (
    <section className="targeta" aria-label={`Contingut de ${models.find((m) => m.model === d.model)?.nom}`}>
      <p className="petit muted" style={{ margin: 0 }}>Tot és opcional. El que deixis buit es treu del fitxer d’origen de la peça (catàleg). Escriu com parlaries a la botiga: frases curtes.</p>
      <SelectorIdioma idiomes={idiomes} actiu={actiu} setActiu={setIdioma} amb={(x) => !!d.contingut[x] && Object.keys(buit(d.contingut[x])).length > 0} />
      <div className="formulari">
        <label className="camp"><span>Nom</span><input value={c.nom ?? ''} onChange={(e) => posa('nom', e.target.value)} placeholder={placeholder('nom')} /></label>
        <label className="camp"><span>Descripció</span><textarea rows={3} value={c.descripcio ?? ''} onChange={(e) => posa('descripcio', e.target.value)} placeholder={placeholder('descripcio')} /></label>
        <label className="camp"><span>Com queda (ajust)</span><input value={c.ajust ?? ''} onChange={(e) => posa('ajust', e.target.value)} placeholder="Tall ample: si dubtes, tria la talla petita." /><small>Surt a dalt de les talles. És el que més ajuda amb el dubte de talla.</small></label>
        <label className="camp"><span>Guia de talles</span><textarea rows={2} value={c.guia_talles ?? ''} onChange={(e) => posa('guia_talles', e.target.value)} placeholder="Pit: S 104 cm · M 110 cm · L 116 cm" /></label>
        <label className="camp"><span>Cura (una instrucció per línia)</span><textarea rows={3} value={(c.cura ?? []).join('\n')} onChange={(e) => posa('cura', e.target.value.split('\n').map((x) => x.trimStart()).filter((x, i, a) => x || i === a.length - 1))} /></label>
        <fieldset className="sense-vora">
          <legend className="etiqueta-mini">Preguntes freqüents</legend>
          <div className="pila" style={{ gap: 8 }}>
            {faq.map((f, i) => (
              <div key={i} className="faq-fila">
                <label className="camp"><span>Pregunta {i + 1}</span><input value={f.q} onChange={(e) => posa('faq', faq.map((x, j) => (j === i ? { ...x, q: e.target.value } : x)))} /></label>
                <label className="camp"><span>Resposta</span><textarea rows={2} value={f.a} onChange={(e) => posa('faq', faq.map((x, j) => (j === i ? { ...x, a: e.target.value } : x)))} /></label>
                <button type="button" className="boto-petit boto-fantasma" onClick={() => posa('faq', faq.filter((_, j) => j !== i))}>Treu la pregunta {i + 1}</button>
              </div>
            ))}
            <div><button type="button" className="boto-petit" onClick={() => posa('faq', [...faq, { q: '', a: '' }])}>Afegeix una pregunta</button></div>
          </div>
        </fieldset>
        <fieldset className="sense-vora">
          <legend className="etiqueta-mini">Combina amb</legend>
          <div className="xips-tria">
            {models.filter((m) => m.model !== d.model).map((m) => {
              const on = (c.combina ?? []).includes(m.model);
              return <label key={m.model} className={on ? 'on' : undefined}><input type="checkbox" checked={on} onChange={(e) => posa('combina', e.target.checked ? [...(c.combina ?? []), m.model] : (c.combina ?? []).filter((x) => x !== m.model))} />{m.nom}</label>;
            })}
          </div>
          <small className="muted">Consell: a <Link to="/sessions">Sessions</Link> hi ha les peces que més es proven juntes.</small>
        </fieldset>
      </div>
      <div className={`barra-desa${brut ? ' bruta' : ''}`}>
        <span role="status" aria-live="polite" className="petit">{missatge ? <span className={missatge.ok ? 'missatge-ok' : 'missatge-error'}>{missatge.text}</span> : brut ? 'Hi ha canvis sense desar.' : 'Tot desat.'}</span>
        <span className="fila">
          <button type="button" onClick={() => setC(desat)} disabled={!brut || desant}>Desfés</button>
          <button type="button" className="boto-primari" onClick={desa} disabled={!brut || desant}>{desant ? 'Desant…' : `Desa (${actiu.toUpperCase()})`}</button>
        </span>
      </div>
    </section>
  );
}

// ── Vista prèvia ─────────────────────────────────────────────────────────

function Previa({ config, models, model, setModel, idioma, setIdioma, botiga, versio, esborrany }: {
  config: ConfigFitxa; models: ModelFitxa[]; model: string; setModel: (m: string) => void; idioma: string; setIdioma: (i: string) => void;
  botiga?: string; versio: number; esborrany: { model: string; idioma: string; c: ContingutModel } | null;
}) {
  const mock = esMock();
  const { filtre } = useFiltre();
  const qd = useApi((s) => (mock && model ? fitxa.model(model, s) : Promise.resolve(null)), [model, mock, versio]);
  const qa = useApi((s) => (mock && model ? analitica.model(filtre, model, s) : Promise.resolve(null)), [model, mock]);
  const nomsModels = Object.fromEntries(models.map((m) => [m.model, m.nom]));
  const contingut = esborrany && esborrany.model === model && esborrany.idioma === idioma ? esborrany.c : qd.dades?.contingut[idioma] ?? {};
  return (
    <div className="previa-sticky">
      <div className="fila" style={{ marginBottom: 10 }}>
        <label className="sr-only" htmlFor="previa-model">Model de la vista prèvia</label>
        <select id="previa-model" value={model} onChange={(e) => setModel(e.target.value)} style={{ flex: '1 1 140px' }}>{models.map((m) => <option key={m.model} value={m.model}>{m.nom}</option>)}</select>
        <label className="sr-only" htmlFor="previa-idioma">Idioma de la vista prèvia</label>
        <select id="previa-idioma" value={idioma} onChange={(e) => setIdioma(e.target.value)}>{config.idiomes.map((i) => <option key={i} value={i}>{i.toUpperCase()}</option>)}</select>
      </div>
      <div className="mobil">
        <div className="mobil-pantalla">
          {mock ? (
            <FitxaPrevia config={config} idioma={idioma} contingut={contingut} origen={qd.dades?.origen ?? null} detall={qa.dades ?? undefined} nomsModels={nomsModels} />
          ) : (
            <iframe key={`${model}${idioma}${botiga}${versio}`} title={`Vista prèvia de la fitxa de ${nomsModels[model] ?? model}`} src={fitxa.urlPrevisualitza(model, botiga, idioma)} />
          )}
        </div>
      </div>
      <p className="petit muted" style={{ marginTop: 8, textAlign: 'center' }}>
        {mock ? 'Vista prèvia amb els canvis que fas, encara que no estiguin desats.' : 'Vista prèvia de la versió desada. Desa per veure-hi els canvis.'} No compta com a toc.
      </p>
    </div>
  );
}
