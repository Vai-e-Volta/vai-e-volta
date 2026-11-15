import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

    expect(
      await screen.findByRole('heading', { name: 'Que bom te ver de novo!' }),
    ).toBeInTheDocument();
  });

  it('API indisponível na verificação inicial trata a pessoa como não logada', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    renderWithProviders(<AppRoutes />, { route: '/' });

    expect(
      await screen.findByRole('heading', { name: 'Que bom te ver de novo!' }),
    ).toBeInTheDocument();
  });

  it('F-08: Sair chama POST /api/auth/logout e leva ao /login', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (url === '/api/auth/me') return jsonResponse(200, { id: 'u1', username: 'ana_teste' });
      if (url === '/api/auth/logout') return new Response(null, { status: 204 });
      throw new Error(`URL inesperada: ${url}`);
    });
    const user = userEvent.setup();
    const { queryClient } = renderWithProviders(<AppRoutes />, { route: '/alugueis' });
    await screen.findByRole('heading', { name: 'Aluguéis' });
    queryClient.setQueryData(['rentals', 'renter', 'active'], [{ id: 'r1' }]);

    await user.click(screen.getByRole('button', { name: 'Sair' }));

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Que bom te ver de novo!' })).toBeInTheDocument(),
    );
    const [, options] = fetchMock.mock.calls.find(([url]) => url === '/api/auth/logout');
    expect(options.method).toBe('POST');
    expect(queryClient.getQueryData(['rentals', 'renter', 'active'])).toBeUndefined();
    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument();

    // Depois de sair, entrar de novo não volta para a tela onde a pessoa estava.
    fetchMock.mockImplementation(async (url) => {
      if (url === '/api/auth/login') return jsonResponse(200, { id: 'u1' });
      if (url === '/api/auth/me') return jsonResponse(200, { id: 'u1', username: 'ana_teste' });
      throw new Error(`URL inesperada: ${url}`);
    });
    await user.type(screen.getByLabelText(/E-mail ou nome de usuário/), 'ana_teste');
    await user.type(screen.getByLabelText(/^Senha/), 'Senha@123');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('heading', { name: 'Itens para alugar' })).toBeInTheDocument();
  });

  it('F-08: se a API falhar ao sair, a sessão local é encerrada mesmo assim', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (url === '/api/auth/me') return jsonResponse(200, { id: 'u1', username: 'ana_teste' });
      throw new TypeError('Failed to fetch');
    });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/' });
    await screen.findByRole('heading', { name: 'Itens para alugar' });

    await user.click(screen.getByRole('button', { name: 'Sair' }));

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Que bom te ver de novo!' })).toBeInTheDocument(),
    );
  });

  it('páginas públicas não mostram o botão Sair para quem não está logado', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Faça login.' } }),
    );

    renderWithProviders(<AppRoutes />, { route: '/rota-que-nao-existe' });

    expect(await screen.findByRole('heading', { name: /não encontrada/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument();
  });
});
