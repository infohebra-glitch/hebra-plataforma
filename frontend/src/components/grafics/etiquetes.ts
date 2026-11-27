/**
 * On va el nom de cada punt perquè cap nom no tapi un punt ni un altre nom.
 * Prova a la dreta i a l'esquerra del punt i després una mica més amunt o avall (el nom queda lligat al punt
 * amb una línia fina). Si no hi cap enlloc, tria el lloc que menys tapa.
 * És el mateix algorisme que l'informe en PDF (hebra/grafics_svg.py, `col_loca_noms`).
 */
export interface Caixa { x0: number; y0: number; x1: number; y1: number; dreta: boolean }

type Rect = [number, number, number, number];

export function colocaNoms(pos: [number, number][], llargs: number[], limits: Rect, fixos: Rect[] = [],
  radi = 8, alt = 14, sep = 10): Caixa[] {
  const [lx0, ly0, lx1, ly1] = limits;
  const obstacles: Rect[] = [...pos.map(([cx, cy]) => [cx - radi, cy - radi, cx + radi, cy + radi] as Rect), ...fixos];
  const tapa = (c: Rect, o: Rect) => {
    const w = Math.min(c[2], o[2]) - Math.max(c[0], o[0]);
    const h = Math.min(c[3], o[3]) - Math.max(c[1], o[1]);
    return w > 0 && h > 0 ? w * h : 0;
  };
  const desplaca = [0, -alt - 2, alt + 2, -2 * alt - 4, 2 * alt + 4, -3 * alt - 6, 3 * alt + 6];
  const ordre = pos.map((_, k) => k).sort((a, b) => pos[a][1] - pos[b][1] || pos[a][0] - pos[b][0]);
  const sortida: Caixa[] = new Array(pos.length);
  const posats: Rect[] = [];
  for (const k of ordre) {
    const [cx, cy] = pos[k];
    const llarg = llargs[k] + 4;
    let millor: Caixa | null = null, cost = Infinity;
    for (const d of desplaca) {
      for (const dreta of [true, false]) {
        const x0 = dreta ? cx + sep : cx - sep - llarg;
        const c: Rect = [x0, cy + d - alt / 2, x0 + llarg, cy + d + alt / 2];
        const fora = Math.max(0, lx0 - c[0]) + Math.max(0, c[2] - (lx1 + 10)) + Math.max(0, ly0 - 4 - c[1])
          + Math.max(0, c[3] - ly1 - 2);
        const cc = obstacles.reduce((s, o) => s + tapa(c, o), 0) + posats.reduce((s, o) => s + tapa(c, o), 0) * 2
          + fora * 50 + Math.abs(d) * 0.01;
        if (cc < cost) { cost = cc; millor = { x0: c[0], y0: c[1], x1: c[2], y1: c[3], dreta }; }
      }
      if (cost < 1) break;
    }
    sortida[k] = millor!;
    posats.push([millor!.x0, millor!.y0, millor!.x1, millor!.y1]);
  }
  return sortida;
}
