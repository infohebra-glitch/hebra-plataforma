/** Targetes de cabina (Provadors en directe) i franja compacta (web del dependent). */
import { useEffect, useState } from 'react';
import type { CabinaDirecte } from '../api/types';
import { enter, hora, segons } from '../lib/format';
import { NOM_ESTAT, faTemps } from '../lib/useCabines';

/** Forma diferent per a cada estat: el color no és l'única pista. */
const SIMBOL: Record<CabinaDirecte['estat'], string> = { ocupada: '●', lliure: '○', porta_oberta: '◐', sense_dades: '×' };

export function useAra(ms = 5000) {
  const [ara, setAra] = useState(Date.now());
  useEffect(() => { const i = window.setInterval(() => setAra(Date.now()), ms); return () => window.clearInterval(i); }, [ms]);
  return ara;
}

export function EstatCabina({ estat }: { estat: CabinaDirecte['estat'] }) {
  return <span className={`estat-cabina ${estat}`}><span aria-hidden="true">{SIMBOL[estat]}</span>{NOM_ESTAT[estat]}</span>;
}

/** Peces del mateix model en talles diferents dins la cabina: el client dubta de talla. */
export function dubteDins(c: CabinaDirecte): string | null {
  const per = new Map<string, Set<string>>();
  for (const p of c.peces) {
    if (!p.nom || !p.talla) continue; // EPC fora del catàleg
    const s = per.get(p.nom) ?? new Set<string>(); s.add(p.talla); per.set(p.nom, s);
  }
  const d = [...per.entries()].find(([, s]) => s.size > 1);
  return d ? `${d[0]} en ${[...d[1]].join(' i ')}` : null;
}

export function TargetaCabina({ c, nova, ara }: { c: CabinaDirecte; nova?: boolean; ara: number }) {
  const dubte = dubteDins(c);
  return (
    <li className={`targeta cabina ${c.estat}${nova ? ' canviada' : ''}`} aria-label={`${c.nom}: ${NOM_ESTAT[c.estat]}`}>
      <div className="targeta-cap">
        <h3>{c.nom}</h3>
        <EstatCabina estat={c.estat} />
      </div>
      <p className="petit muted" style={{ margin: 0 }}>
        {c.estat === 'sense_dades' ? <>No arriben dades des de {c.des_de ? faTemps(c.des_de, ara) : 'fa més de 2 h'}. Mira que el lector estigui endollat.</> :
          <>{NOM_ESTAT[c.estat]} des de les {c.des_de ? hora(c.des_de) : '—'} ({faTemps(c.des_de, ara)})</>}
      </p>
      {c.estat !== 'sense_dades' && (
        <div>
          <div className="etiqueta-mini">Peces dins {c.peces.length ? `(${c.peces.length})` : ''}</div>
          {c.peces.length ? (
            <ul className="peces-cabina">
              {c.peces.map((p) => <li key={p.epc}><span>{p.nom ?? 'Peça sense catàleg'}</span><span className="muted">{p.color ?? ''}</span><b className="talla-xip">{p.talla ?? '—'}</b></li>)}
            </ul>
          ) : <p className="petit muted" style={{ margin: '2px 0 0' }}>Cap peça llegida al darrer minut.</p>}
          {dubte && <p className="petit" style={{ margin: '6px 0 0' }}><span className="insignia insignia-alerta">Dubte de talla</span> {dubte}: potser cal ajudar-la.</p>}
        </div>
      )}
      {c.peticions_obertes > 0 && <p style={{ margin: 0 }}><span className="insignia insignia-critic">{c.peticions_obertes === 1 ? '1 petició oberta' : `${c.peticions_obertes} peticions obertes`}</span></p>}
      <dl className="avui-cabina">
        <div><dt>Sessions avui</dt><dd>{enter(c.avui.sessions)}</dd></div>
        <div><dt>Proves avui</dt><dd>{enter(c.avui.proves)}</dd></div>
        <div><dt>Durada mitjana</dt><dd>{segons(c.avui.durada_mitjana_s)}</dd></div>
      </dl>
    </li>
  );
}

export function FranjaCabines({ cabines, ara }: { cabines: CabinaDirecte[]; ara: number }) {
  if (!cabines.length) return null;
  return (
    <ul className="franja-cabines" aria-label="Estat de les cabines">
      {cabines.map((c) => (
        <li key={c.cabina_id} className={`xip-cabina ${c.estat}`}>
          <b>{c.nom.replace('Cabina ', 'C')}</b>
          <EstatCabina estat={c.estat} />
          <span className="petit muted">{c.estat === 'ocupada' ? `${c.peces.length} ${c.peces.length === 1 ? 'peça' : 'peces'} · ${faTemps(c.des_de, ara).replace('fa ', '')}` : c.estat === 'sense_dades' ? 'revisar lector' : faTemps(c.des_de, ara)}</span>
        </li>
      ))}
    </ul>
  );
}
