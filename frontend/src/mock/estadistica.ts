/** Utilitats del mode demostració: atzar reproduïble i la prova de dues proporcions. */

/** Atzar determinista a partir d'un text (mateixa llavor → mateixos números). */
export function atzar(llavor: string): () => number {
  let h = 1779033703 ^ llavor.length;
  for (let i = 0; i < llavor.length; i++) {
    h = Math.imul(h ^ llavor.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Funció de distribució de la normal estàndard (aproximació d'Abramowitz-Stegun). */
function phi(z: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp((-z * z) / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return z > 0 ? 1 - p : p;
}

export interface ResultatProva { diferencia: number; ic95: [number, number]; p_valor: number; proves_necessaries: number }

/** Prova z de dues proporcions, IC 95 % de la diferència i mostra per a potència 0,8. */
export function provaDuesProporcions(x1: number, n1: number, x2: number, n2: number): ResultatProva | null {
  if (n1 === 0 || n2 === 0) return null;
  const p1 = x1 / n1, p2 = x2 / n2, d = p1 - p2;
  const p = (x1 + x2) / (n1 + n2);
  const seZ = Math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2));
  const z = seZ === 0 ? 0 : d / seZ;
  const se = Math.sqrt((p1 * (1 - p1)) / n1 + (p2 * (1 - p2)) / n2);
  const nGrup = d === 0 ? Infinity : Math.ceil(((1.96 + 0.8416) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))) / (d * d));
  return {
    diferencia: d,
    ic95: [d - 1.96 * se, d + 1.96 * se],
    p_valor: 2 * (1 - phi(Math.abs(z))),
    proves_necessaries: Number.isFinite(nGrup) ? nGrup * 2 : 99999,
  };
}
