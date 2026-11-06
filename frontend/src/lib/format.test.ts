import { describe, expect, it } from 'vitest';
import { decimal, enter, eur, pct, punts, pValorEnParaules, segons, rang } from './format';
import { calculaPeriode } from './periode';

const nb = (s: string) => s.replace(/ | /g, ' ');

describe('format', () => {
  it('enters amb punt de milers', () => {
    expect(enter(1234)).toBe('1.234');
    expect(enter(538)).toBe('538');
    expect(enter(null)).toBe('—');
  });
  it('percentatges de fraccions', () => {
    expect(nb(pct(0.34))).toBe('34 %');
    expect(nb(pct(0.037, 1))).toBe('3,7 %');
    expect(pct(null)).toBe('—');
  });
  it('euros', () => {
    expect(nb(eur(69))).toBe('69 €');
    expect(nb(eur(1280))).toBe('1.280 €');
  });
  it('punts percentuals amb signe', () => {
    expect(punts(0.03)).toBe('+3 punts');
    expect(punts(-0.016, 1)).toBe('−1,6 punts');
    expect(punts(0.01)).toBe('+1 punt');
    expect(punts(0)).toBe('0 punts');
  });
  it('decimals i segons', () => {
    expect(decimal(1.6)).toBe('1,6');
    expect(segons(92)).toBe('92 s');
    expect(segons(340)).toBe('5 min 40 s');
    expect(segons(null)).toBe('—');
  });
  it('p-valor en paraules', () => {
    expect(pValorEnParaules(0.11)).toContain('no és concloent');
    expect(pValorEnParaules(0.003)).toContain('Molt improbable');
    expect(pValorEnParaules(null)).toContain('Encara no');
  });
  it('rang de dates', () => {
    expect(rang('2026-11-16', '2026-11-22')).toBe('del 16 de nov. al 22 de nov.');
  });
});

describe('periode', () => {
  const dijous = new Date(2026, 10, 5, 10); // dijous 5-11-2026
  it('aquesta setmana comença dilluns', () => {
    expect(calculaPeriode('aquesta', dijous)).toEqual({ des: '2026-11-02', fins: '2026-11-05' });
  });
  it('setmana passada de dilluns a diumenge', () => {
    expect(calculaPeriode('passada', dijous)).toEqual({ des: '2026-10-26', fins: '2026-11-01' });
  });
  it('darrers 30 dies inclou avui', () => {
    expect(calculaPeriode('trenta', dijous)).toEqual({ des: '2026-10-07', fins: '2026-11-05' });
  });
});
