/**
 * Vista prèvia de la fitxa del client (mode demostració). Reprodueix el que
 * pinta hebra/templates/fitxa.html amb la configuració que s'està editant, sense
 * desar res ni registrar cap esdeveniment. Amb backend, es fa servir l'iframe de
 * GET /fitxa/previsualitza (la versió desada).
 */
import type { ConfigFitxa, ContingutModel, ModelDetall } from '../api/types';
import { contrast } from '../lib/fitxa';
import { motiuFitxa, textFitxa } from '../lib/textosFitxa';

interface Etapa { etapa?: string; pais?: string; regio?: string }
interface Comp { material?: string; pct?: number; pais?: string }

export function FitxaPrevia({ config, idioma, contingut, origen, detall, nomsModels }: {
  config: ConfigFitxa; idioma: string; contingut: ContingutModel; origen: Record<string, unknown> | null;
  detall?: ModelDetall; nomsModels: Record<string, string>;
}) {
  const t = (k: string) => textFitxa(idioma, k);
  const ap = config['aparença'];
  const color = /^#[0-9A-Fa-f]{6}$/.test(ap.color_principal) ? ap.color_principal : '#214F46';
  const textBoto = contrast(color, '#FFFFFF') >= 4.5 ? '#FFFFFF' : '#1d201f';
  const nom = contingut.nom || (origen?.nom as string) || detall?.nom || 'Peça';
  const descripcio = contingut.descripcio || (origen?.descripcio as string) || '';
  const cura = contingut.cura?.length ? contingut.cura : (origen?.cura as string[] | undefined) ?? [];
  const etapes = (origen?.etapes as Etapa[] | undefined) ?? [];
  const comp = (origen?.composicio as Comp[] | undefined) ?? [];
  const talles = detall?.talles ?? [];
  const actual = talles[Math.floor(talles.length / 2)]?.talla;
  const estoc = config.accions.mostra_estoc;

  const seccio = (s: string) => {
    if (!config.seccions.visibles[s as keyof ConfigFitxa['seccions']['visibles']]) return null;
    switch (s) {
      case 'talles':
        return (
          <section key={s} className="fp-panell">
            <h2>{t('talles')}</h2>
            {contingut.ajust && <p className="fp-petit">{contingut.ajust}</p>}
            <div className="fp-talles">
              {talles.map((x) => (
                <span key={x.talla} className={`fp-talla${x.talla === actual ? ' actual' : ''}${x.estoc === 0 ? ' esgotada' : ''}`}>
                  {x.talla}
                  {estoc !== 'no' && x.talla !== actual && <small>{x.estoc === 0 ? t('esgotada') : estoc === 'unitats' ? `${x.estoc} ${t('unitats')}` : '✓'}</small>}
                </span>
              ))}
            </div>
            {contingut.guia_talles && <p className="fp-petit"><b>{t('guia')}:</b> {contingut.guia_talles}</p>}
            {config.accions.demana_talla && <button type="button" tabIndex={-1} className="fp-boto" style={{ background: color, color: textBoto, borderColor: color }}>{t('demana')}</button>}
          </section>
        );
      case 'composicio':
        return comp.length ? (
          <section key={s} className="fp-panell"><h2>{t('composicio')}</h2>
            <ul>{comp.map((c, i) => <li key={i}>{Math.round((c.pct ?? 0) * 100)} % {c.material}{c.pais ? ` · ${c.pais}` : ''}</li>)}</ul>
          </section>
        ) : null;
      case 'origen':
        return etapes.length ? (
          <section key={s} className="fp-panell"><h2>{t('origen')}</h2>
            <p>{etapes.map((e) => e.pais).join(' → ')}</p>
            <span className="fp-enllac" style={{ color }}>{t('veure_origen')}</span>
            <p className="fp-nota">Només els dies que la prova d’origen ho permet.</p>
          </section>
        ) : null;
      case 'cura':
        return cura.length ? <section key={s} className="fp-panell"><h2>{t('cura')}</h2><ul>{cura.map((c) => <li key={c}>{c}</li>)}</ul></section> : null;
      case 'combina':
        return contingut.combina?.length ? (
          <section key={s} className="fp-panell"><h2>{t('combina')}</h2><ul>{contingut.combina.map((m) => <li key={m}>{nomsModels[m] ?? m}</li>)}</ul></section>
        ) : null;
      case 'faq':
        return contingut.faq?.length ? (
          <section key={s} className="fp-panell"><h2>{t('faq')}</h2>{contingut.faq.map((f, i) => <details key={i}><summary>{f.q}</summary><p>{f.a}</p></details>)}</section>
        ) : null;
      default: return null;
    }
  };

  return (
    <div className="fp" lang={idioma}>
      <div className="fp-cap">
        {ap.logo_data_url ? <img src={ap.logo_data_url} alt={ap.nom_marca} className="fp-logo" /> : <span className="fp-marca" style={{ color }}>{ap.nom_marca || 'Marca'}</span>}
        <span className="fp-idiomes">{config.idiomes.map((i) => <span key={i} className={i === idioma ? 'actiu' : undefined} style={i === idioma ? { borderColor: color } : undefined}>{i.toUpperCase()}</span>)}</span>
      </div>
      {config.textos.benvinguda?.[idioma] && <p className="fp-benvinguda">{config.textos.benvinguda[idioma]}</p>}
      <h1>{nom}</h1>
      {detall && <p className="fp-petit">{detall.color}{actual ? ` · ${actual}` : ''} · {Math.round(detall.preu)} €</p>}
      {descripcio && <p>{descripcio}</p>}
      {config.seccions.ordre.map(seccio)}
      {config.accions.demana_assistencia && (
        <section className="fp-panell fp-assist">
          <button type="button" tabIndex={-1} className="fp-boto fp-boto-sec" style={{ color, borderColor: color }}>{t('assistencia')}</button>
          <p className="fp-petit">{t('assistencia_ajuda')}</p>
        </section>
      )}
      {config.accions.per_que_no && config.motius.length > 0 && (
        <section className="fp-panell"><h2>{t('per_que')}</h2><p className="fp-petit">{t('per_que_ajuda')}</p>
          <div className="fp-motius">{config.motius.map((m) => <span key={m} className="fp-xip">{motiuFitxa(idioma, m)}</span>)}</div>
        </section>
      )}
      {config.textos.peu?.[idioma] && <p className="fp-peu">{config.textos.peu[idioma]}</p>}
      <p className="fp-nota">{t('privacitat')}</p>
    </div>
  );
}
