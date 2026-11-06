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
      <div className="entrada-caixa">
        <span className="marca-hebra"><LogoHebra mida={28} />Hebra</span>
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
    </main>
  );
}
