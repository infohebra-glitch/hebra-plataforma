/** Diàleg «Envia per correu»: destinataris separats per comes; valida abans d'enviar. */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { llegeixCorreus } from '../lib/programacio';

export function DialegCorreu({ obert, titol, inicial = [], enTanca, envia }: {
  obert: boolean; titol: string; inicial?: string[]; enTanca: () => void; envia: (destinataris: string[]) => Promise<unknown>;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState(inicial.join(', '));
  const [error, setError] = useState<string | null>(null);
  const [fet, setFet] = useState<string | null>(null);
  const [enviant, setEnviant] = useState(false);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (obert && !d.open) { setText(inicial.join(', ')); setError(null); setFet(null); d.showModal(); }
    if (!obert && d.open) d.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [obert]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const { correus, dolents } = llegeixCorreus(text);
    if (dolents.length) { setError(`Aquest correu no sembla vàlid: ${dolents[0]}`); return; }
    if (!correus.length) { setError('Escriu com a mínim un correu.'); return; }
    setEnviant(true); setError(null);
    try { await envia(correus); setFet(`Enviat a ${correus.join(', ')}.`); }
    catch (err) { setError((err as Error).message); } finally { setEnviant(false); }
  };
  return (
    <dialog ref={ref} className="dialeg" aria-labelledby="titol-correu" onClose={enTanca}>
      <form className="formulari" onSubmit={submit} noValidate>
        <h2 id="titol-correu">Envia per correu</h2>
        <p className="muted" style={{ margin: 0 }}>{titol}. S’hi adjunta el PDF.</p>
        <label className="camp"><span>Destinataris</span>
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="encarregada@marca.cat, producte@marca.cat" rows={3} aria-describedby="ajuda-correu" autoFocus />
          <small id="ajuda-correu">Separa’ls amb comes. Només correus de l’equip: mai de clients.</small>
        </label>
        <div role="status" aria-live="polite">
          {error && <p className="missatge-error" role="alert">{error}</p>}
          {fet && <p className="missatge-ok">{fet}</p>}
        </div>
        <div className="fila" style={{ justifyContent: 'flex-end' }}>
          <button type="button" onClick={enTanca}>{fet ? 'Tanca' : 'Cancel·la'}</button>
          {!fet && <button type="submit" className="boto-primari" disabled={enviant}>{enviant ? 'Enviant…' : 'Envia'}</button>}
        </div>
      </form>
    </dialog>
  );
}
