/** Icones de traç (18 px), decoratives: sempre van amb text al costat. */
const camins: Record<string, string> = {
  resum: 'M3 12h4l3-8 4 16 3-8h4',
  peces: 'M8 3 4 6l2 4 2-1v12h8V9l2 1 2-4-4-3c-.5 1.5-2 2.5-4 2.5S8.5 4.5 8 3Z',
  talles: 'M4 7h16M4 12h16M4 17h10M8 4v6M14 4v6',
  perque: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-2.5-11.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14m0 3h.01',
  origen: 'M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11Zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  servei: 'M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z',
  estoc: 'M3 8 12 3l9 5v8l-9 5-9-5V8Zm0 0 9 5 9-5M12 13v8',
  decisions: 'M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9',
  valor: 'M17 6.5A6 6 0 1 0 17 17.5M4 10h9M4 14h9',
  informes: 'M7 3h7l5 5v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm7 0v5h5M9 13h6M9 17h6',
  dades: 'M12 3v12m0 0-4-4m4 4 4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2',
  dependent: 'M7 3h10a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm4 15h2',
  sessions: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  provadors: 'M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17M3 21h18M9 3v18M13 12h2',
  fitxa: 'M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm3 4h6M9 11h6M9 15h3',
  amunt: 'M12 19V5M6 11l6-6 6 6',
  avall: 'M12 5v14M6 13l6 6 6-6',
  correu: 'M4 6h16v12H4V6Zm0 0 8 7 8-7',
  baixa: 'M12 4v11m0 0-4-4m4 4 4-4M5 20h14',
  refresca: 'M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7',
  mes: 'M4 6h16M4 12h16M4 18h16',
  surt: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3',
  afegeix: 'M12 5v14M5 12h14',
  edita: 'M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4ZM14 6l4 4',
  paperera: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  prova: 'M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3M7.5 14h9',
  imprimeix: 'M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v7H7v-7Z',
};

export function Icona({ nom, mida = 18 }: { nom: keyof typeof camins | string; mida?: number }) {
  return (
    <svg width={mida} height={mida} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={camins[nom] ?? camins.resum} />
    </svg>
  );
}

/** Camí del monograma de Hebra (traçat del logo oficial, marca/paleta-2026-11/logo-blau.png). */
export const CAMI_LOGO = 'M3.7 734.3C3.3 589.9 3.0 366.2 3.0 237.3L3.0 2.9L36.2 3.3L69.5 3.7L95.5 7.9C201.4 25.0 257.6 35.4 323.5 50.1C467.4 82.3 568.8 120.4 618.8 160.9C622.2 163.7 625.2 166.0 625.5 166.0C625.8 166.0 626.0 129.3 626.0 84.5L626.0 3.0L655.4 3.0L684.9 3.0L685.2 286.8C685.4 442.8 685.4 666.5 685.2 783.8L684.9 997.0L656.0 997.0L627.2 997.0L604.8 982.6C434.3 872.9 63.8 635.0 63.4 635.0C63.2 635.0 63.0 716.5 63.0 816.0L63.0 997.0L33.7 997.0L4.3 997.0L3.7 734.3ZM626.0 783.5L626.0 642.0L625.2 642.1C624.8 642.1 590.4 683.6 548.7 734.2L472.9 826.3L473.8 827.2C474.7 828.1 625.2 925.0 625.8 925.0C625.9 925.0 626.0 861.3 626.0 783.5ZM443.6 768.2C455.1 754.1 491.2 710.3 523.6 671.0C556.1 631.6 582.9 598.9 583.4 598.2L584.1 597.0L350.1 596.8L116.0 596.5L116.2 597.2C116.5 597.9 421.2 794.0 422.0 793.9C422.3 793.9 432.0 782.3 443.6 768.2ZM626.0 437.4L626.0 337.8L618.9 344.1C553.3 403.0 438.3 460.0 254.0 525.0C236.7 531.1 222.4 536.3 222.1 536.6C221.9 536.8 312.6 537.0 423.8 537.0L626.0 537.0L626.0 437.4ZM105.0 511.8C325.7 442.1 478.1 376.9 556.0 318.7L569.5 308.6L582.1 296.1L594.8 283.5L599.8 275.7C602.6 271.4 605.9 265.3 607.1 262.2L609.3 256.5L609.4 249.4L609.4 242.3L605.7 234.8L602.0 227.3L595.4 220.1L588.8 213.0L579.7 206.2C564.0 194.4 548.5 185.5 526.3 175.2C442.4 136.3 300.3 100.7 108.5 70.5C89.2 67.5 71.1 64.6 68.2 64.1L63.0 63.3L63.0 294.1L63.0 524.9L68.2 523.3C71.1 522.5 87.7 517.3 105.0 511.8Z';

/** El monograma de Hebra (el del logo de la marca, vectoritzat). Pren el color del text. */
export function LogoHebra({ mida = 22, titol, classe }: { mida?: number; titol?: string; classe?: string }) {
  return (
    <svg height={mida} width={Math.round(mida * 0.69)} viewBox="-1 -1 690 1001" role={titol ? 'img' : undefined}
      aria-hidden={titol ? undefined : true} aria-label={titol} focusable="false" className={classe ?? 'logo-hebra'}>
      <path fill="currentColor" fillRule="evenodd" d={CAMI_LOGO} />
    </svg>
  );
}
