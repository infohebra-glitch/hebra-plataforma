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
  imprimeix: 'M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v7H7v-7Z',
};

export function Icona({ nom, mida = 18 }: { nom: keyof typeof camins | string; mida?: number }) {
  return (
    <svg width={mida} height={mida} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={camins[nom] ?? camins.resum} />
    </svg>
  );
}

export function LogoHebra({ mida = 22 }: { mida?: number }) {
  return (
    <svg width={mida} height={mida} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="7" fill="var(--traca)" />
      <path d="M9 8v16M23 8v16M9 16h14" stroke="var(--lli)" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
