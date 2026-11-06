import { useState, type FormEvent } from 'react';
import { operacio } from '../api/endpoints';
import type { ResultatImport, ResultatShopify } from '../api/types';
import { TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { enter, plural } from '../lib/format';

type Tipus = 'vendes' | 'estoc' | 'cataleg';
const TIPUS: { tipus: Tipus; nom: string; descripcio: string; columnes: string; nomesAdmin?: boolean }[] = [
  { tipus: 'vendes', nom: 'Vendes', descripcio: 'Les vendes del TPV, per atribuir compres a les proves.', columnes: 'data_hora, botiga, gtin, quantitat' },
  { tipus: 'estoc', nom: 'Estoc', descripcio: 'Les unitats que hi ha a cada botiga ara mateix.', columnes: 'botiga, gtin, unitats' },
  { tipus: 'cataleg', nom: 'Catàleg', descripcio: 'Models, talles, colors i preus.', columnes: 'gtin, model, nom, categoria, color, talla, preu', nomesAdmin: true },
];

function Importador({ t }: { t: (typeof TIPUS)[number] }) {
  const [fitxer, setFitxer] = useState<File | null>(null);
  const [resultat, setResultat] = useState<ResultatImport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviant, setEnviant] = useState(false);
  const envia = async (e: FormEvent) => {
    e.preventDefault();
    if (!fitxer) return;
    setEnviant(true); setError(null); setResultat(null);
    try { setResultat(await operacio.importa(t.tipus, fitxer)); } catch (err) { setError((err as Error).message); } finally { setEnviant(false); }
  };
  const id = `fitxer-${t.tipus}`;
  return (
    <form className="targeta" onSubmit={envia}>
      <h3>{t.nom}</h3>
      <p className="muted" style={{ margin: 0 }}>{t.descripcio}</p>
      <p className="petit" style={{ margin: 0 }}>Columnes: <span className="codi">{t.columnes}</span></p>
      <label className="camp" htmlFor={id}><span>Fitxer CSV</span></label>
      <input id={id} type="file" accept=".csv,text/csv" onChange={(e) => { setFitxer(e.target.files?.[0] ?? null); setResultat(null); setError(null); }} />
      <div><button type="submit" className="boto-primari" disabled={!fitxer || enviant}>{enviant ? 'Important…' : `Importa ${t.nom.toLowerCase()}`}</button></div>
      <div role="status" aria-live="polite">
        {resultat && (
          <div className={resultat.errors.length ? 'avis-estimacio' : 'avis'}>
            <b>{resultat.importades ? `${plural(resultat.importades, 'fila importada', 'files importades')}.` : 'No s’ha importat cap fila.'}</b>
            {resultat.errors.length > 0 && (
              <>
                <p className="petit" style={{ margin: '4px 0' }}>{plural(resultat.errors.length, 'fila amb error', 'files amb errors')} (no s’han importat):</p>
                <ul className="petit" style={{ margin: 0, paddingLeft: 18, maxHeight: 160, overflowY: 'auto' }}>{resultat.errors.slice(0, 50).map((x, i) => <li key={i}>{x}</li>)}</ul>
                {resultat.errors.length > 50 && <p className="petit muted">… i {enter(resultat.errors.length - 50)} més.</p>}
              </>
            )}
          </div>
        )}
        {error && <p className="missatge-error" role="alert">{error}</p>}
      </div>
    </form>
  );
}

function Shopify() {
  const { filtre } = useFiltre();
  const [r, setR] = useState<ResultatShopify | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviant, setEnviant] = useState(false);
  const sincronitza = async () => {
    setEnviant(true); setError(null); setR(null);
    try { setR(await operacio.sincronitzaShopify(filtre.botiga)); } catch (e) { setError((e as Error).message); } finally { setEnviant(false); }
  };
  return (
    <div className="targeta">
      <h3>Shopify</h3>
      <p className="muted" style={{ margin: 0 }}>Porta les comandes i l’estoc de la botiga en línia. {filtre.botiga ? `Botiga: ${filtre.botiga}.` : 'Totes les botigues.'}</p>
      <div><button type="button" onClick={sincronitza} disabled={enviant}>{enviant ? 'Sincronitzant…' : 'Sincronitza ara'}</button></div>
      <div role="status" aria-live="polite">
        {r && <p className="missatge-ok">Fet: {plural(r.comandes, 'comanda', 'comandes')}, {plural(r.linies, 'línia', 'línies')} i {plural(r.estoc, 'registre', 'registres')} d’estoc.</p>}
        {error && <p className="missatge-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

export function Dades() {
  const { usuari } = useSessio();
  const admin = usuari.rol === 'admin';
  return (
    <>
      <TitolPagina titol="Importa dades" senseperiode>Fitxers CSV de vendes, estoc i catàleg. Separador coma o punt i coma, codificació UTF-8, amb capçalera a la primera fila.</TitolPagina>
      <div className="reixa-3">
        {TIPUS.filter((t) => !t.nomesAdmin || admin).map((t) => <Importador key={t.tipus} t={t} />)}
      </div>
      {admin && <div className="seccio"><h2 style={{ marginBottom: 12 }}>Sincronització</h2><div className="reixa-3"><Shopify /></div></div>}
    </>
  );
}
