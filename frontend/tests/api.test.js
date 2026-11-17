import { describe, expect, it, vi } from 'vitest';
import { ApiError, api, getCurrentUser, setUnauthorizedHandler } from '../src/services/api';
import { jsonResponse } from './renderWithProviders';

describe('services/api', () => {
  it('usa caminho relativo /api, credentials same-origin e corpo JSON', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(201, { id: 1 }));

    const data = await api.post('/auth/register', { username: 'ana' });

    expect(data).toEqual({ id: 1 });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/auth/register');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('same-origin');
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(options.body)).toEqual({ username: 'ana' });
  });

  it('lê o formato de erro {error: {code, message, fields}}', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(409, {
        error: {
          code: 'FIELD_IN_USE',
          message: 'Um dos campos já está em uso.',
          fields: { email: 'Este campo já está cadastrado.' },
        },
      }),
    );

    const error = await api.post('/auth/register', {}).catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.code).toBe('FIELD_IN_USE');
    expect(error.message).toBe('Um dos campos já está em uso.');
    expect(error.fields).toEqual({ email: 'Este campo já está cadastrado.' });
  });

  it('usa mensagem genérica quando a resposta de erro não é JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('Bad Gateway', { status: 502 }));

    const error = await api.get('/listings').catch((caught) => caught);

    expect(error.code).toBe('INTERNAL_ERROR');
    expect(error.message).toMatch(/Não foi possível/);
    expect(error.fields).toEqual({});
  });

  it('converte falha de rede em ApiError sem detalhes técnicos', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await api.get('/listings').catch((caught) => caught);

    expect(error.code).toBe('NETWORK_ERROR');
    expect(error.message).not.toMatch(/Failed to fetch/);
  });

  it('em 401 chama o handler de sessão expirada', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Sessão expirada.' } }),
    );
    const handler = vi.fn();
    const unregister = setUnauthorizedHandler(handler);

    await expect(api.get('/me/rentals')).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledTimes(1);
    unregister();
  });

  it('a verificação inicial da sessão não dispara o handler de 401', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(401, undefined));
    const handler = vi.fn();
    const unregister = setUnauthorizedHandler(handler);

    await expect(getCurrentUser()).rejects.toMatchObject({ status: 401 });
    expect(handler).not.toHaveBeenCalled();
    unregister();
  });

  it('retorna null em 204', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));

    await expect(api.delete('/listings/1/favorite')).resolves.toBeNull();
  });
});
