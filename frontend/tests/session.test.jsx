import { act, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { api } from '../src/services/api';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

describe('sessão', () => {
  it('um 401 em qualquer chamada limpa a sessão e leva ao /login', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(200, { id: 'u1', username: 'ana_teste' }));

    renderWithProviders(<AppRoutes />, { route: '/notificacoes' });
    expect(await screen.findByRole('heading', { name: 'Notificações' })).toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(
      jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Sessão expirada.' } }),
    );
    await act(async () => {
      await api.get('/notifications').catch(() => {});
    });

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
  });

  it('API indisponível na verificação inicial trata a pessoa como não logada', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    renderWithProviders(<AppRoutes />, { route: '/' });

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
  });
});
