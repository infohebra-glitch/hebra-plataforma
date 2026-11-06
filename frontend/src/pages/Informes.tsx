import { Link } from 'react-router-dom';
import { TitolPagina } from '../components/TitolPagina';
import { Icona } from '../components/Icones';
import { INFORMES } from '../lib/etiquetes';

export function Informes() {
  return (
    <>
      <TitolPagina titol="Informes">Documents d’una pàgina per llegir, imprimir o desar en PDF. Fan servir la botiga i el període triats a dalt.</TitolPagina>
      <ul className="llista-targetes reixa-2" style={{ display: 'grid' }}>
        {INFORMES.map((i) => (
          <li key={i.tipus} className="targeta">
            <div className="targeta-cap"><h3>{i.nom}</h3><span className="insignia insignia-neutra">{i.per}</span></div>
            <p className="muted" style={{ margin: 0 }}>{i.descripcio}</p>
            <div><Link className="boto" to={`/informes/${i.tipus}`}><Icona nom="informes" />Obre l’informe</Link></div>
          </li>
        ))}
      </ul>
      <p className="petit muted" style={{ marginTop: 16 }}>Les alertes en temps real no són un informe: les veu el personal a la <Link to="/dependent">web del dependent</Link>.</p>
    </>
  );
}
