import { afterEach, describe, expect, it, vi } from 'vitest';
import { ErrorApi, api, configuraNoAutenticat, configuraTransport, construeixUrl, paramsFiltre } from './client';

const json = (cos: unknown, status = 200) => new Response(JSON.stringify(cos), { status, headers: { 'Content-Type': 'application/json' } });

afterEach(() => { configuraTransport((u, i) => fetch(u, i)); });

describe('client de l’API', () => {
  it('construeix la URL amb el filtre comú i sense buits', () => {
    expect(construeixUrl('/resum', paramsFiltre({ botiga: 'BCN-01', des: '2026-11-16', fins: '2026-11-22' })))
      .toBe('/api/v2/resum?botiga=BCN-01&des=2026-11-16&fins=2026-11-22');
    expect(construeixUrl('/resum', paramsFiltre({ des: '2026-11-16' }))).toBe('/api/v2/resum?des=2026-11-16');
  });

  it('envia galetes i JSON', async () => {
    const t = vi.fn(async () => json({ ok: true }));
    configuraTransport(t);
    await api.post('/decisions', { titol: 'x' });
    const [url, init] = t.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/v2/decisions');
    expect(init.credentials).toBe('same-origin');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
    expect(init.body).toBe('{"titol":"x"}');
  });

  it('401 crida la redirecció a /app/entra', async () => {
    const redirigeix = vi.fn();
    configuraNoAutenticat(redirigeix);
    configuraTransport(async () => json({ detail: 'Cal entrar.' }, 401));
    await expect(api.get('/resum')).rejects.toBeInstanceOf(ErrorApi);
    expect(redirigeix).toHaveBeenCalledOnce();
  });

  it('401 a POST /sessio (contrasenya errònia) no redirigeix', async () => {
    const redirigeix = vi.fn();
    configuraNoAutenticat(redirigeix);
    configuraTransport(async () => json({ detail: 'El correu o la contrasenya no són correctes.' }, 401));
    await expect(api.post('/sessio', {})).rejects.toThrow('El correu o la contrasenya no són correctes.');
    expect(redirigeix).not.toHaveBeenCalled();
  });

  it('fa servir el detail en català dels errors', async () => {
    configuraTransport(async () => json({ detail: 'Aquest model no existeix.' }, 404));
    await expect(api.get('/models/X')).rejects.toMatchObject({ estat: 404, message: 'Aquest model no existeix.' });
  });

  it('sense xarxa dona un missatge entenedor', async () => {
    configuraTransport(async () => { throw new TypeError('Failed to fetch'); });
    await expect(api.get('/resum')).rejects.toMatchObject({ estat: 0 });
  });

  it('puja fitxers com a multipart amb el camp «fitxer»', async () => {
    const t = vi.fn(async () => json({ importades: 2, errors: [] }));
    configuraTransport(t);
    await api.puja('/importa/vendes', new File(['a,b\n1,2'], 'v.csv'));
    const init = (t.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get('fitxer')).toBeInstanceOf(File);
  });
});
