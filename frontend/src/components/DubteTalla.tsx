/** «Dubte de talla»: el mateix model en dues talles a la mateixa sessió, i quina s'acaba comprant. */
import type { ParellTalla } from '../api/types';
import { enter } from '../lib/format';

export const EXPLICACIO_DUBTE = 'Quan algú s’emporta a la cabina la mateixa peça en dues talles, és que la guia de talles o el patró no li deixen clar quina és la seva. Si passa sovint, i sobretot si acaba comprant la talla gran (o cap), val la pena revisar la guia de talles de la fitxa o el patró.';

/** Barra apilada horitzontal: quina talla s'ha comprat de cada parell (o cap). */
export function BarraCompra({ p }: { p: ParellTalla }) {
  const parts = Object.entries(p.comprada);
  const total = parts.reduce((s, [, n]) => s + n, 0) || 1;
  const [ta] = p.talles.split('+');
  return (
    <div className="barra-compra" aria-hidden="true">
      {parts.map(([t, n]) => n > 0 && (
        <span key={t} className={t === 'cap' ? 'cap' : t === ta ? 'a' : 'b'} style={{ width: `${(n / total) * 100}%` }} title={`${t === 'cap' ? 'Cap' : t}: ${n}`}>{(n / total) > 0.14 ? (t === 'cap' ? 'cap' : t) : ''}</span>
      ))}
    </div>
  );
}

export function textCompra(p: ParellTalla): string {
  return Object.entries(p.comprada).map(([t, n]) => (t === 'cap' ? `${enter(n)} sense comprar` : `${enter(n)} la ${t}`)).join(', ');
}

export function TaulaParells({ parells, ambModel }: { parells: ParellTalla[]; ambModel?: boolean }) {
  return (
    <div className="taula-wrap"><table>
      <caption className="sr-only">Parells de talles provats a la mateixa sessió i quina s’ha comprat</caption>
      <thead><tr>{ambModel && <th scope="col">Model</th>}<th scope="col">Talles</th><th scope="col" className="n">Sessions</th><th scope="col" style={{ minWidth: 180 }}>Què s’han emportat</th></tr></thead>
      <tbody>{parells.map((p) => (
        <tr key={`${p.model ?? ''}${p.talles}`}>
          {ambModel && <td><b>{p.nom ?? p.model}</b></td>}
          <td><b>{p.talles.replace('+', ' i ')}</b></td>
          <td className="n">{enter(p.sessions)}{p.mostra_petita && <> <span className="insignia insignia-mostra" title="Menys de 10 sessions">Mostra petita</span></>}</td>
          <td><BarraCompra p={p} /><span className="petit muted">{textCompra(p)}</span></td>
        </tr>
      ))}</tbody>
    </table></div>
  );
}

export function llegendaCompra() {
  return (
    <ul className="llegenda">
      <li><span className="clau-quadre bg-s1" aria-hidden="true" />Talla petita del parell</li>
      <li><span className="clau-quadre bg-s2" aria-hidden="true" />Talla gran</li>
      <li><span className="clau-quadre bg-neutra" aria-hidden="true" />No n’ha comprat cap</li>
    </ul>
  );
}

