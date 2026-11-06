import { describe, expect, it } from 'vitest';
import { descriuProgramacio, llegeixCorreus, properaExecucio, textPropera } from './programacio';
import { aplicaTema, desaTema, llegeixTema } from './tema';
import { liftEnParaules, maxEix, sostre, ticks } from './escala';

const base = { actiu: true, dia_setmana: null, dia_mes: null, data: null, hora: '08:00' } as const;
// Dijous 5 de novembre del 2026, 10:00 (hora local)
const ARA = new Date(2026, 10, 5, 10, 0);

describe('programació d’informes', () => {
  it('diari: demà si l’hora ja ha passat, avui si no', () => {
    expect(properaExecucio({ ...base, tipus: 'diari' }, ARA)).toEqual(new Date(2026, 10, 6, 8, 0));
    expect(properaExecucio({ ...base, tipus: 'diari', hora: '18:30' }, ARA)).toEqual(new Date(2026, 10, 5, 18, 30));
  });
  it('setmanal: el proper dilluns (0 = dilluns)', () => {
    expect(properaExecucio({ ...base, tipus: 'setmanal', dia_setmana: 0 }, ARA)).toEqual(new Date(2026, 10, 9, 8, 0));
    // el mateix dijous, però l'hora ja ha passat → d'aquí a 7 dies
    expect(properaExecucio({ ...base, tipus: 'setmanal', dia_setmana: 3 }, ARA)).toEqual(new Date(2026, 10, 12, 8, 0));
  });
  it('mensual: el dia del mes vinent si ja ha passat', () => {
    expect(properaExecucio({ ...base, tipus: 'mensual', dia_mes: 1 }, ARA)).toEqual(new Date(2026, 11, 1, 8, 0));
    expect(properaExecucio({ ...base, tipus: 'mensual', dia_mes: 20 }, ARA)).toEqual(new Date(2026, 10, 20, 8, 0));
  });
  it('una vegada: null si la data ja ha passat o està desactivada', () => {
    expect(properaExecucio({ ...base, tipus: 'temporada', data: '2027-02-15' }, ARA)).toEqual(new Date(2027, 1, 15, 8, 0));
    expect(properaExecucio({ ...base, tipus: 'temporada', data: '2026-01-15' }, ARA)).toBeNull();
    expect(properaExecucio({ ...base, tipus: 'diari', actiu: false }, ARA)).toBeNull();
  });
  it('ho diu en paraules', () => {
    expect(descriuProgramacio({ ...base, tipus: 'setmanal', dia_setmana: 0 })).toMatch(/^Cada dilluns a les 08:00/);
    expect(textPropera(new Date(2026, 10, 5, 18, 0), ARA)).toBe('avui a les 18:00');
    expect(textPropera(new Date(2026, 10, 6, 8, 0), ARA)).toBe('demà a les 08:00');
    expect(textPropera(null, ARA)).toBe('No es tornarà a generar');
  });
  it('llegeix correus i separa els que no són vàlids', () => {
    expect(llegeixCorreus('a@marca.cat, b@marca.cat; malament\na@marca.cat')).toEqual({ correus: ['a@marca.cat', 'b@marca.cat'], dolents: ['malament'] });
  });
});

describe('tema', () => {
  const magatzem = (inicial: string | null) => { let v = inicial; return { getItem: () => v, setItem: (_: string, x: string) => { v = x; } }; };
  it('per defecte és clar, també amb l’antic «sistema» o sense emmagatzematge', () => {
    expect(llegeixTema(magatzem(null))).toBe('clar');
    expect(llegeixTema(magatzem('sistema'))).toBe('clar');
    expect(llegeixTema(null)).toBe('clar');
    expect(llegeixTema({ getItem: () => { throw new Error('bloquejat'); }, setItem: () => {} })).toBe('clar');
  });
  it('desa i recupera el fosc; si desar falla, no peta', () => {
    const m = magatzem(null);
    desaTema('fosc', m);
    expect(llegeixTema(m)).toBe('fosc');
    expect(() => desaTema('fosc', { getItem: () => null, setItem: () => { throw new Error('ple'); } })).not.toThrow();
  });
  it('posa data-theme', () => {
    const el = { dataset: {} as DOMStringMap };
    aplicaTema('fosc', el); expect(el.dataset.theme).toBe('dark');
    aplicaTema('clar', el); expect(el.dataset.theme).toBe('light');
  });
});

describe('escales dels gràfics', () => {
  it('arrodoneix el sostre', () => {
    expect(sostre(0)).toBe(1);
    expect(sostre(7)).toBe(10);
    expect(sostre(180)).toBe(200);
    expect(sostre(0.23)).toBe(0.25);
  });
  it('les fraccions no passen del 100 %', () => {
    expect(maxEix([0.95, 0.4], 'pct')).toBe(1);
    expect(maxEix([0.3], 'pct')).toBe(0.5);
    expect(maxEix([null, 42], 'enter')).toBe(50);
    expect(ticks(100)).toEqual([0, 25, 50, 75, 100]);
    expect(ticks(50)).toEqual([0, 10, 20, 30, 40, 50]);
    expect(ticks(1)).toEqual([0, 0.25, 0.5, 0.75, 1]);
  });
  it('explica el lift', () => {
    expect(liftEnParaules(2.1)).toBe('Es proven juntes 2,1 vegades més del que tocaria per casualitat.');
    expect(liftEnParaules(1)).toMatch(/més o menys/);
    expect(liftEnParaules(null)).toMatch(/no es pot/);
  });
});

import { combina, contrast, mou, validaLogo } from './fitxa';
import { aplicaCabina } from './useCabines';
import type { CabinaDirecte, ConfigFitxa, ProvadorsDirecte } from '../api/types';

describe('fitxa NFC', () => {
  it('mou seccions amunt i avall sense sortir dels límits', () => {
    expect(mou(['a', 'b', 'c'], 1, -1)).toEqual(['b', 'a', 'c']);
    expect(mou(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'b', 'c']);
  });
  it('valida el logo (PNG/SVG, ≤ 100 KB)', () => {
    expect(validaLogo({ type: 'image/png', size: 40_000 })).toBeNull();
    expect(validaLogo({ type: 'image/jpeg', size: 1000 })).toMatch(/PNG o SVG/);
    expect(validaLogo({ type: 'image/svg+xml', size: 150_000 })).toMatch(/100 KB/);
  });
  it('calcula el contrast WCAG', () => {
    expect(contrast('#000000', '#FFFFFF')).toBeCloseTo(21, 0);
    expect(contrast('#214F46', '#FFFFFF')).toBeGreaterThan(4.5);
  });
  it('la config de botiga només sobreescriu els grups que porta', () => {
    const g = { idiomes: ['ca', 'es'], accions: { demana_talla: true, demana_assistencia: true, per_que_no: true, mostra_estoc: 'no' } } as unknown as ConfigFitxa;
    const r = combina(g, { idiomes: ['es'], accions: { mostra_estoc: 'unitats' } });
    expect(r.idiomes).toEqual(['es']);
    expect(r.accions).toEqual({ demana_talla: true, demana_assistencia: true, per_que_no: true, mostra_estoc: 'unitats' });
    expect(g.idiomes).toEqual(['ca', 'es']);
  });
});

describe('cabines en directe', () => {
  it('aplica un esdeveniment «cabina» i recalcula el resum', () => {
    const c = (id: string, estat: CabinaDirecte['estat'], s = 1): CabinaDirecte => ({ cabina_id: id, nom: id, botiga_id: 'B', estat, des_de: null, peces: [], peticions_obertes: 0, avui: { sessions: s, proves: 2 * s, durada_mitjana_s: 300 } });
    const d: ProvadorsDirecte = { generat: '', cabines: [c('C1', 'lliure'), c('C2', 'ocupada')], resum: { ocupades: 1, lliures: 1, sessions_avui: 2, proves_avui: 4 } };
    const r = aplicaCabina(d, c('C1', 'ocupada', 3));
    expect(r.resum).toEqual({ ocupades: 2, lliures: 0, sessions_avui: 4, proves_avui: 8 });
    expect(aplicaCabina(d, c('C3', 'lliure')).cabines).toHaveLength(3);
  });
});
