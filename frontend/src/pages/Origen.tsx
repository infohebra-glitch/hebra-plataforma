import { useRef, useState, type FormEvent } from 'react';
import { analitica, operacio } from '../api/endpoints';
import { Buit, Consulta, Esquelet } from '../components/Estat';
import { TargetaExperiment } from '../components/Experiment';
import { Rajola } from '../components/Rajola';
import { Barres } from '../components/grafics/Barres';
import { Seccio, TitolPagina } from '../components/TitolPagina';
import { useFiltre } from '../context/Filtre';
import { useSessio } from '../context/Sessio';
import { idioma, seccio } from '../lib/etiquetes';
import { decimal, enter, isoData } from '../lib/format';
import { useApi } from '../lib/useApi';

export function Origen() {
  const { filtre, clau } = useFiltre();
  const qe = useApi((s) => analitica.experiments(filtre, s), [clau]);
  const qn = useApi((s) => analitica.fitxaNfc(filtre, s), [clau]);
  const dialeg = useRef<HTMLDialogElement>(null);
  return (
    <>
      <TitolPagina titol="Origen i proves" accions={<button type="button" className="boto-primari" onClick={() => dialeg.current?.showModal()}>Nova prova</button>}>
        Proves A/B per dies: uns dies la fitxa NFC ensenya un canvi (com l’origen de la peça) i uns altres no. Comparem la conversió dels dos grups.
      </TitolPagina>
      <Consulta q={qe} esquelet={<Esquelet tipus="grafic" />}>
        {(r) => r.experiments.length ? (
          <div className="pila">{r.experiments.map((e) => <TargetaExperiment key={e.id} e={e} />)}</div>
        ) : <div className="panell"><Buit titol="Encara no hi ha cap prova" accio={<button type="button" onClick={() => dialeg.current?.showModal()}>Crea la primera prova</button>}>Una prova compara dies amb un canvi i dies sense. Comença per l’origen: és la que més pregunta la direcció.</Buit></div>}
      </Consulta>

      <Seccio titol="Ús de la fitxa NFC" subtitol="Què miren els clients quan toquen l’etiqueta amb el mòbil, i en quin idioma.">
        <Consulta q={qn} esquelet={<Esquelet tipus="rajoles" />}>
          {(n) => (
            <>
              <div className="rajoles">
                <Rajola etiqueta="Tocs a la fitxa" valor={enter(n.tocs)} nota={<>en {enter(n.sessions_cabina)} sessions de cabina</>} />
                <Rajola etiqueta="Tocs per sessió" valor={decimal(n.tocs_per_sessio)} nota="mitjana" />
              </div>
              <div className="reixa-2" style={{ marginTop: 16 }}>
                <div className="panell"><h3>Seccions consultades</h3><p className="petit muted">Percentatge sobre {enter(n.tocs)} tocs.</p>
                  <Barres titol="Seccions" items={n.seccions.map((s) => ({ clau: s.seccio, etiqueta: seccio(s.seccio), n: s.n, pct: s.pct }))} /></div>
                <div className="panell"><h3>Idioma del mòbil</h3><p className="petit muted">Percentatge sobre {enter(n.tocs)} tocs.</p>
                  <Barres titol="Idiomes" items={n.idiomes.map((s) => ({ clau: s.idioma, etiqueta: idioma(s.idioma), n: s.n, pct: s.pct }))} /></div>
              </div>
            </>
          )}
        </Consulta>
      </Seccio>
      <dialog ref={dialeg} className="dialeg" aria-labelledby="titol-nova-prova">
        <NovaProva enTanca={() => { dialeg.current?.close(); qe.recarrega(); }} />
      </dialog>
    </>
  );
}

function NovaProva({ enTanca }: { enTanca: () => void }) {
  const { botigues } = useSessio();
  const [error, setError] = useState<string | null>(null);
  const [enviant, setEnviant] = useState(false);
  const envia = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setEnviant(true); setError(null);
    try {
      await operacio.creaExperiment({
        id: String(f.get('id')), botiga_id: String(f.get('botiga_id')), variable: String(f.get('variable')), hipotesi: String(f.get('hipotesi')),
        unitat: 'dia', inici: String(f.get('inici')), setmanes: Number(f.get('setmanes')), proves_minimes: Number(f.get('proves_minimes')),
      });
      enTanca();
    } catch (err) { setError((err as Error).message); } finally { setEnviant(false); }
  };
  return (
    <form className="formulari" method="dialog" onSubmit={envia}>
      <h2 id="titol-nova-prova">Nova prova A/B</h2>
      <p className="petit muted" style={{ margin: 0 }}>En crear-la, el servidor sorteja quins dies van a cada grup.</p>
      <div className="dues">
        <label className="camp"><span>Identificador</span><input name="id" required placeholder="origen-2027-01" pattern="[a-z0-9-]+" /><small>Minúscules, xifres i guions.</small></label>
        <label className="camp"><span>Què canvia</span>
          <select name="variable" defaultValue="origen"><option value="origen">L’origen a la fitxa</option><option value="preu">El preu</option><option value="exposicio">L’exposició</option><option value="peticio_talla">La petició de talla</option></select>
        </label>
      </div>
      <label className="camp"><span>Hipòtesi</span><textarea name="hipotesi" required placeholder="Ensenyar l’origen fa que se la quedin més sovint." /></label>
      <div className="dues">
        <label className="camp"><span>Botiga</span><select name="botiga_id">{botigues.map((b) => <option key={b.id} value={b.id}>{b.nom}</option>)}</select></label>
        <label className="camp"><span>Inici</span><input name="inici" type="date" required defaultValue={isoData(new Date())} /></label>
        <label className="camp"><span>Setmanes</span><input name="setmanes" type="number" min={2} max={12} defaultValue={6} required /><small>Entre 4 i 8 és el que sol caldre.</small></label>
        <label className="camp"><span>Mínim de proves per grup</span><input name="proves_minimes" type="number" min={10} defaultValue={30} required /></label>
      </div>
      {error && <p className="missatge-error" role="alert">{error}</p>}
      <div className="fila" style={{ justifyContent: 'flex-end' }}>
        <button type="button" onClick={enTanca}>Cancel·la</button>
        <button type="submit" className="boto-primari" disabled={enviant}>{enviant ? 'Creant…' : 'Crea la prova'}</button>
      </div>
    </form>
  );
}
