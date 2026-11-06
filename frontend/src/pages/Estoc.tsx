/** Estoc: parat amb suggeriments i tasques, risc de rebaixa i precisió (D). */
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { analitica, tasques } from '../api/endpoints';
import { desaBlob } from '../api/client';
import type { EstocParat, Tasca } from '../api/types';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { Icona } from '../components/Icones';
import { Rajola } from '../components/Rajola';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { decimal, diaCurt, enter, eur, pct, plural } from '../lib/format';
import { NOMS_ACCIO, nomTipusTasca, tascaDeParat } from '../lib/tasques';
import { useApi } from '../lib/useApi';

type Ordre = 'valor' | 'dies';

export function Estoc() {
  const { filtre, clau } = useFiltre();
  const q = useApi((s) => analitica.estoc(filtre, s), [clau]);
  const qt = useApi((s) => tasques.llista(filtre.botiga, undefined, s), [filtre.botiga]);
  return (
    <>
      <TitolPagina titol="Estoc i tasques">Peces que no es mouen, què en podem fer, i la llista de tasques de cada botiga.</TitolPagina>
      <Consulta q={q} esquelet={<><Esquelet tipus="rajoles" /><div style={{ height: 16 }} /><Esquelet tipus="taula" /></>}>
        {(e) => (
          <>
            <div className="rajoles">
              <Rajola etiqueta="Unitats parades" valor={enter(e.resum_parat?.unitats ?? e.parat.reduce((s, x) => s + x.unitats, 0))} nota={<>en {plural(e.parat.length, 'referència', 'referències')} sense cap prova ni venda en 21 dies</>} />
              {e.resum_parat && <Rajola etiqueta="Valor parat" valor={eur(e.resum_parat.valor_eur)} nota="a preu de venda (PVP)" />}
              <Rajola etiqueta="Models en risc de rebaixa" valor={enter(e.risc_rebaixa.length)} nota="molta cobertura i poca conversió" />
              <Rajola etiqueta="Precisió de l’estoc" valor={e.precisio ? pct(e.precisio.error_mitja_pct, 1) : '—'} nota={e.precisio ? <>error mitjà entre recompte manual i RFID · {enter(e.precisio.recomptes)} recomptes</> : 'Encara cap recompte manual'} />
            </div>
            {e.resum_parat && e.resum_parat.per_categoria.length > 0 && (
              <ul className="xips-categoria" aria-label="Estoc parat per categoria">
                {e.resum_parat.per_categoria.map((c) => <li key={c.categoria}><b>{c.categoria}</b> {plural(c.unitats, 'unitat', 'unitats')} · {eur(c.valor_eur)}</li>)}
              </ul>
            )}
            <Parat files={e.parat} enTasca={() => { q.recarrega(); qt.recarrega(); }} />
            <Seccio titol="Risc de rebaixa" subtitol="Models amb estoc per a més de 8 setmanes al ritme de venda actual i conversió al quartil inferior de la seva categoria.">
              {e.risc_rebaixa.length ? (
                <div className="panell" style={{ padding: 0 }}><div className="taula-wrap"><table>
                  <caption className="sr-only">Risc de rebaixa</caption>
                  <thead><tr><th scope="col">Model</th><th scope="col" className="n">Unitats</th><th scope="col" className="n">Cobertura</th><th scope="col" className="n">Conversió</th></tr></thead>
                  <tbody>{e.risc_rebaixa.map((r) => (
                    <tr key={r.model}><td><Link className="nom-model" to={`/peces/${encodeURIComponent(r.model)}`}>{r.nom}</Link></td><td className="n">{enter(r.unitats)}</td><td className="n">{r.cobertura_setmanes === null ? '—' : `${decimal(r.cobertura_setmanes)} setm.`}</td><td className="n">{pct(r.conversio)}</td></tr>
                  ))}</tbody>
                </table></div></div>
              ) : <div className="panell"><Buit titol="Cap model en risc">Cap model combina molta cobertura amb poca conversió.</Buit></div>}
            </Seccio>
          </>
        )}
      </Consulta>
      <Seccio titol="Tasques de botiga" subtitol="El que cal fer a la botiga. Les veu el personal a la web del dependent i les marca com a fetes.">
        <Consulta q={qt} esquelet={<Esquelet tipus="taula" files={3} />}>
          {(r) => <LlistaTasques tasques={r.tasques} enCanvi={qt.recarrega} />}
        </Consulta>
      </Seccio>
    </>
  );
}

function Parat({ files, enTasca }: { files: EstocParat[]; enTasca: () => void }) {
  const { filtre } = useFiltre();
  const { botigues, usuari } = useSessio();
  const [categoria, setCategoria] = useState('');
  const [ordre, setOrdre] = useState<Ordre>('valor');
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [missatge, setMissatge] = useState<{ ok: boolean; text: string } | null>(null);
  const [enCurs, setEnCurs] = useState(false);
  const clauFila = (p: EstocParat) => `${p.botiga_id ?? ''}|${p.gtin}`;
  const nomBotiga = (id: string | null | undefined) => botigues.find((b) => b.id === id)?.nom ?? id ?? '';
  const curt = (id: string | null | undefined) => nomBotiga(id).split(' · ')[0];
  const categories = [...new Set(files.map((p) => p.categoria).filter(Boolean))] as string[];
  const visibles = useMemo(() => files.filter((p) => !categoria || p.categoria === categoria).sort((a, b) =>
    ordre === 'valor' ? (b.valor_eur ?? 0) - (a.valor_eur ?? 0) : (b.dies_parat ?? b.dies_sense_activitat) - (a.dies_parat ?? a.dies_sense_activitat)), [files, categoria, ordre]);
  const seleccionables = visibles.filter((p) => !p.tasca && p.suggeriment);
  const triades = seleccionables.filter((p) => sel.has(clauFila(p)));
  const mostraBotiga = !filtre.botiga && usuari.rol !== 'botiga';

  const crea = async (llista: EstocParat[]) => {
    setEnCurs(true); setMissatge(null);
    try {
      for (const p of llista) await tasques.crea(tascaDeParat(p, filtre.botiga ?? usuari.botiga_id ?? '', curt(p.suggeriment?.botiga_desti)));
      setSel(new Set());
      setMissatge({ ok: true, text: llista.length === 1 ? 'Tasca creada. La veuran a la web del dependent.' : `${plural(llista.length, 'tasca creada', 'tasques creades')}. Les veuran a la web del dependent.` });
      enTasca();
    } catch (e) { setMissatge({ ok: false, text: `No s’ha pogut crear: ${(e as Error).message}` }); } finally { setEnCurs(false); }
  };
  const csv = async () => {
    try { desaBlob(await analitica.estocParatCsv({ ...filtre, categoria: categoria || undefined }), `estoc-parat${filtre.botiga ? `-${filtre.botiga}` : ''}.csv`); }
    catch (e) { setMissatge({ ok: false, text: `No s’ha pogut descarregar: ${(e as Error).message}` }); }
  };
  const commuta = (k: string) => setSel((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const totes = triades.length === seleccionables.length && seleccionables.length > 0;

  return (
    <Seccio titol="Estoc parat" subtitol="Unitats amb 0 proves i 0 vendes en els darrers 21 dies, amb què et proposem fer-ne. Crea una tasca i la botiga la veurà a la seva llista.">
      <div className="barra-eines">
        <label className="camp-linia"><span>Categoria</span>
          <select value={categoria} onChange={(e) => { setCategoria(e.target.value); setSel(new Set()); }}>
            <option value="">Totes</option>{categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="camp-linia"><span>Ordena per</span>
          <select value={ordre} onChange={(e) => setOrdre(e.target.value as Ordre)}><option value="valor">Valor (€)</option><option value="dies">Dies parat</option></select>
        </label>
        <span style={{ flex: 1 }} />
        <button type="button" onClick={csv}><Icona nom="baixa" />Descarrega CSV</button>
        <button type="button" className="boto-primari" disabled={!triades.length || enCurs} onClick={() => crea(triades)}>
          {triades.length ? `Crea tasques per als ${triades.length} seleccionats` : 'Crea tasques per als seleccionats'}
        </button>
      </div>
      <div role="status" aria-live="polite">{missatge && <p className={missatge.ok ? 'missatge-ok' : 'missatge-error'}>{missatge.text}</p>}</div>
      {visibles.length ? (
        <div className="panell" style={{ padding: 0 }}><div className="taula-wrap"><table className="taula-parat">
          <caption className="sr-only">Estoc parat amb suggeriments</caption>
          <thead><tr>
            <th scope="col" style={{ width: 36 }}><input type="checkbox" aria-label="Selecciona tots els que no tenen tasca" checked={totes} disabled={!seleccionables.length} onChange={() => setSel(totes ? new Set() : new Set(seleccionables.map(clauFila)))} /></th>
            <th scope="col">Peça</th>{mostraBotiga && <th scope="col">Botiga</th>}<th scope="col" className="n">Unitats</th><th scope="col" className="n">Valor</th><th scope="col" className="n">Dies</th><th scope="col">Què en podem fer</th>
          </tr></thead>
          <tbody>{visibles.map((p) => {
            const k = clauFila(p);
            return (
              <tr key={k} className={sel.has(k) ? 'seleccionada' : undefined}>
                <td><input type="checkbox" aria-label={`Selecciona ${p.nom} ${p.talla}`} checked={sel.has(k)} disabled={!!p.tasca || !p.suggeriment} onChange={() => commuta(k)} /></td>
                <td><Link className="nom-model" to={`/peces/${encodeURIComponent(p.model)}`}>{p.nom}</Link><div className="petit muted">{[p.color, `talla ${p.talla}`, p.categoria].filter(Boolean).join(' · ')}</div></td>
                {mostraBotiga && <td>{curt(p.botiga_id)}</td>}
                <td className="n">{enter(p.unitats)}</td>
                <td className="n">{eur(p.valor_eur)}</td>
                <td className="n">{enter(p.dies_parat ?? p.dies_sense_activitat)}</td>
                <td className="suggeriment">
                  {p.suggeriment ? (
                    <>
                      <span className={`insignia accio-${p.suggeriment.accio}`}>{NOMS_ACCIO[p.suggeriment.accio] ?? p.suggeriment.accio}</span>
                      <span className="text-sugg">{p.suggeriment.text}</span>
                      {(p.proves_altres_botigues ?? 0) > 0 && <span className="petit muted">A les altres botigues: {plural(p.proves_altres_botigues ?? 0, 'prova', 'proves')}, {plural(p.vendes_altres_botigues ?? 0, 'venda', 'vendes')}.</span>}
                      {p.tasca ? <span className="insignia insignia-bo">✓ Tasca {p.tasca.estat === 'pendent' ? 'creada' : p.tasca.estat}</span>
                        : <button type="button" className="boto-petit" disabled={enCurs} onClick={() => crea([p])}>Crea la tasca</button>}
                    </>
                  ) : <span className="muted">—</span>}
                </td>
              </tr>
            );
          })}</tbody>
        </table></div></div>
      ) : <div className="panell"><Buit titol="Res parat">{categoria ? 'Cap peça parada en aquesta categoria.' : 'Totes les unitats en estoc s’han provat o venut en els darrers 21 dies.'}</Buit></div>}
      <details className="veure-taula" style={{ marginTop: 10 }}>
        <summary>Com triem el suggeriment</summary>
        <ul className="petit" style={{ margin: '6px 0 0', paddingLeft: 18, maxWidth: '75ch' }}>
          <li><b>Traspassar</b>: en una altra botiga es prova o es ven més.</li>
          <li><b>Treure a la sala</b>: no s’ha provat mai aquí i hi ha unitats; probablement no és visible.</li>
          <li><b>Promoció</b> o <b>revisar</b>: es prova però no es ven (mira’n els motius).</li>
          <li><b>Retornar</b>: fa més de 60 dies que no es mou enlloc.</li>
        </ul>
      </details>
    </Seccio>
  );
}

export function LlistaTasques({ tasques: llista, enCanvi }: { tasques: Tasca[]; enCanvi: () => void }) {
  const { botigues, usuari } = useSessio();
  const [veureFetes, setVeureFetes] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pendents = llista.filter((t) => t.estat === 'pendent');
  const tancades = llista.filter((t) => t.estat !== 'pendent');
  const nom = (id: string | null) => botigues.find((b) => b.id === id)?.nom ?? id ?? '';
  const canvia = async (t: Tasca, estat: 'feta' | 'descartada') => {
    setError(null);
    try { await tasques.canvia(t.id, estat); enCanvi(); } catch (e) { setError((e as Error).message); }
  };
  const fila = (t: Tasca) => (
    <li key={t.id} className={`targeta tasca ${t.estat}`}>
      <div className="targeta-cap">
        <div style={{ minWidth: 0 }}>
          <b>{t.titol}</b>
          <div className="petit muted">{nomTipusTasca(t.tipus)}{usuari.rol !== 'botiga' && ` · ${nom(t.botiga_id)}`}{t.botiga_desti && botigues.some((b) => b.id === t.botiga_desti) && ` → ${nom(t.botiga_desti)}`} · creada el {diaCurt(t.creada)}{t.feta && ` · ${t.estat} el ${diaCurt(t.feta)}`}</div>
        </div>
        {t.estat === 'pendent' ? (
          <div className="fila">
            <button type="button" className="boto-petit" onClick={() => canvia(t, 'descartada')}>Descarta</button>
            <button type="button" className="boto-petit boto-primari" onClick={() => canvia(t, 'feta')}>Feta</button>
          </div>
        ) : <span className={`insignia ${t.estat === 'feta' ? 'insignia-bo' : 'insignia-mostra'}`}>{t.estat === 'feta' ? '✓ Feta' : 'Descartada'}</span>}
      </div>
      {t.detall && <p className="petit" style={{ margin: 0 }}>{t.detall}</p>}
    </li>
  );
  return (
    <>
      {error && <p className="missatge-error" role="alert">{error}</p>}
      {pendents.length ? <ul className="llista-targetes">{pendents.map(fila)}</ul>
        : <div className="panell"><Buit titol="Cap tasca pendent">Crea’n des de l’estoc parat, amb el botó «Crea la tasca».</Buit></div>}
      {tancades.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <button type="button" className="boto-fantasma boto-petit" aria-expanded={veureFetes} onClick={() => setVeureFetes(!veureFetes)}>{veureFetes ? 'Amaga les fetes i descartades' : `Veure les fetes i descartades (${tancades.length})`}</button>
          {veureFetes && <ul className="llista-targetes" style={{ marginTop: 8 }}>{tancades.map(fila)}</ul>}
        </div>
      )}
    </>
  );
}
