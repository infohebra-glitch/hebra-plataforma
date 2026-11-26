/**
 * v0.5: la peça de roba com a protagonista. Foto (o silueta de la categoria) i una
 * minisèrie de tendència per a les targetes de la galeria.
 */
import { Link } from 'react-router-dom';
import { enter } from '../lib/format';

export function FotoPeca({ src, nom, mida = 'mitjana', className = '' }: { src?: string | null; nom: string; mida?: 'mini' | 'petita' | 'mitjana' | 'gran'; className?: string }) {
  return (
    <span className={`foto-peca foto-${mida} ${className}`}>
      {src ? <img src={src} alt={nom} loading="lazy" decoding="async" /> : <span className="foto-buida" aria-hidden="true" />}
    </span>
  );
}

/** Línia petita de tendència (sense eixos): el valor exacte va al text de la targeta. */
export function Sparkline({ valors, titol, amplada = 120, alcada = 32 }: { valors: number[]; titol: string; amplada?: number; alcada?: number }) {
  if (valors.length < 2) return null;
  const max = Math.max(1, ...valors);
  const pas = amplada / (valors.length - 1);
  const punts = valors.map((v, i) => `${(i * pas).toFixed(1)},${(alcada - 3 - (v / max) * (alcada - 6)).toFixed(1)}`);
  const total = valors.reduce((a, b) => a + b, 0);
  return (
    <svg className="sparkline" width={amplada} height={alcada} viewBox={`0 0 ${amplada} ${alcada}`} role="img" aria-label={`${titol}: ${enter(total)} en total, màxim de ${enter(max)} en un dia`}>
      <polyline points={`0,${alcada} ${punts.join(' ')} ${amplada},${alcada}`} className="sparkline-area" />
      <polyline points={punts.join(' ')} className="sparkline-linia" />
    </svg>
  );
}

/** Miniatures enllaçades d'altres peces (p. ex. «Es prova amb»). */
export function FilaPeces({ peces }: { peces: { model: string; nom: string; imatge?: string; nota: string }[] }) {
  return (
    <ul className="fila-peces">
      {peces.map((p) => (
        <li key={p.model}>
          <Link to={`/peces/${encodeURIComponent(p.model)}`}>
            <FotoPeca src={p.imatge} nom={p.nom} mida="petita" />
            <span className="nom">{p.nom}</span>
            <span className="nota">{p.nota}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
