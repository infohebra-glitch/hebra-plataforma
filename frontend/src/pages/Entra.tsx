import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { sessio } from '../api/endpoints';
import { LogoHebra } from '../components/Icones';
import { esMock } from '../lib/mode';

export function Entra() {
  const [correu, setCorreu] = useState('');
  const [contrasenya, setContrasenya] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enviant, setEnviant] = useState(false);
  const navega = useNavigate();
  const [q] = useSearchParams();
  useEffect(() => { document.title = 'Entra · Hebra'; }, []);

  const envia = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setEnviant(true);
    try {
      const r = await sessio.entra(correu.trim(), contrasenya);
      const torna = q.get('torna')?.replace(/^\/app/, '') || (r.usuari.rol === 'botiga' ? '/dependent' : '/');
      navega(torna.startsWith('/') && !torna.startsWith('//') ? torna : '/', { replace: true });
    } catch (err) {
      setError((err as Error).message || 'No hem pogut entrar. Torna-ho a provar.');
    } finally {
      setEnviant(false);
    }
  };

  return (
    <main className="entrada">
      <section className="entrada-marca" aria-hidden="true">
        <span className="marca-hebra"><LogoHebra mida={30} />Hebra</span>
        <div>
          <h2>El que passa al provador, per fi a la vista.</h2>
          <p>Cada prova, cada talla que falta i cada peça que no es compra, al costat de les vendes de la botiga.</p>
          <ul className="entrada-dades">
            <li><b>Provat</b><span>què entra a la cabina</span></li>
            <li><b>Venut</b><span>què acaba a caixa</span></li>
            <li><b>Per què no</b><span>el que diu el client</span></li>
          </ul>
        </div>
        <LogoHebra classe="monograma" mida={900} />
      </section>
      <div className="entrada-form">
      <div className="entrada-caixa">
        <span className="marca-hebra marca-mobil"><LogoHebra mida={28} />Hebra</span>
        <div>
          <h1>Entra al tauler</h1>
          <p className="muted">Provat, venut, convertit: el que passa als provadors de les teves botigues.</p>
        </div>
        <form className="panell formulari" onSubmit={envia} noValidate>
          <label className="camp"><span>Correu electrònic</span>
            <input type="email" name="correu" autoComplete="username" required value={correu} onChange={(e) => setCorreu(e.target.value)} aria-invalid={!!error} />
          </label>
          <label className="camp"><span>Contrasenya</span>
            <input type="password" name="contrasenya" autoComplete="current-password" required value={contrasenya} onChange={(e) => setContrasenya(e.target.value)} aria-invalid={!!error} />
          </label>
          {error && <p className="missatge-error" role="alert" style={{ margin: 0 }}>{error}</p>}
          <button type="submit" className="boto-primari" disabled={enviant || !correu || !contrasenya}>{enviant ? 'Entrant…' : 'Entra'}</button>
        </form>
        {esMock() && <p className="avis petit">Mode demostració: qualsevol correu i contrasenya serveixen. Amb un correu que comenci per «botiga» entres com a dependent.</p>}
        <p className="petit muted">Si no recordes la contrasenya, demana-la a l’administrador de la teva marca.</p>
      </div>
      </div>
    </main>
  );
}
