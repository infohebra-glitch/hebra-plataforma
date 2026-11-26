/**
 * Fotos de producte de la demostració (v0.5). Són imatges generades per a la demo,
 * no peces reals de cap marca. En el mode demo d'un sol fitxer s'incrusten com a data URL.
 */
import camisa from './camisa.jpg';
import faldilla from './faldilla.jpg';
import jersei from './jersei.jpg';
import pantalo from './pantalo.jpg';
import sobrecamisa from './sobrecamisa.jpg';
import texans from './texans.jpg';
import vestit from './vestit.jpg';

export const FOTOS: Record<string, string> = {
  'CL-24-NAT': camisa,
  'VV-26-VRD': vestit,
  'TX-26-IND': texans,
  'JM-24-GRF': jersei,
  'SB-25-CRU': sobrecamisa,
  'PL-26-TER': pantalo,
  'FA-26-BLA': faldilla,
};

/** Fotos que la marca ha canviat o esborrat durant la demo (model → data URL; '' = silueta). */
export const fotosPropies = new Map<string, string>();

const SILUETA = 'data:image/svg+xml,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500"><rect width="400" height="500" fill="#F1EFEE"/>'
  + '<path d="M150 70l-70 40-40 90 50 25 20-40v255h180V185l20 40 50-25-40-90-70-40c-10 25-30 38-50 38s-40-13-50-38z" fill="#B7B3B2"/></svg>');

export function foto(model: string): string {
  const p = fotosPropies.get(model);
  if (p !== undefined) return p || SILUETA;
  return FOTOS[model] ?? SILUETA;
}
export const teFoto = (model: string) => (fotosPropies.get(model) ?? FOTOS[model] ?? '') !== '';
