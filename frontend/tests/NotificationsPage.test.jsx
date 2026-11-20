import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const NOTIFICATIONS = [
  {
    id: 'n1',
    type: 'proposal_received',
    payload: {
      rental_id: 'r1',
      listing_id: 7,
      listing_title: 'Barraca',
      renter_username: 'davi_teste',
      start_date: '2026-12-01',
      end_date: '2026-12-03',
    },
    created_at: '2026-11-20T10:00:00-03:00',
    read_at: null,
  },
  {
    id: 'n2',
    type: 'proposal_expired',
    payload: { rental_id: 'r2', listing_id: 8, listing_title: 'Furadeira' },
    created_at: '2026-11-19T10:00:00-03:00',
    read_at: '2026-11-19T11:00:00-03:00',
  },
];

function mockApi({ unread = 1 } = {}) {
  let count = unread;
  let rows = NOTIFICATIONS;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/notifications/unread-count') return jsonResponse(200, { count });
    if (url.startsWith('/api/notifications?')) {
      return jsonResponse(200, { items: rows, next_cursor: null });
    }
    if (url === '/api/notifications/n1/read' && method === 'POST') {
      count = 0;
      rows = rows.map((row) => ({ ...row, read_at: row.read_at ?? '2026-11-20T12:00:00-03:00' }));
      return new Response(null, { status: 204 });
    }
    if (url === '/api/notifications/read-all' && method === 'POST') {
      count = 0;
      rows = rows.map((row) => ({ ...row, read_at: row.read_at ?? '2026-11-20T12:00:00-03:00' }));
      return new Response(null, { status: 204 });
    }
    if (
      url.startsWith('/api/me/') ||
      url.startsWith('/api/listings') ||
      url === '/api/categories'
    ) {
      return jsonResponse(200, { items: [], next_cursor: null, total: 0 });
    }
    if (url.startsWith('/api/tags')) return jsonResponse(200, []);
    throw new Error(`URL inesperada: ${method} ${url}`);
  });
}

describe('sino e caixa de notificações (F-46, F-47, F-52, RN-67)', () => {
  it('o sino mostra quantos avisos novos há e leva à caixa', async () => {
    mockApi({ unread: 3 });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    const bell = await screen.findByRole('link', { name: 'Notificações, 3 novas' });
    await user.click(bell);

    expect(await screen.findByRole('heading', { name: 'Notificações' })).toBeInTheDocument();
  });

  it('sem avisos novos, o sino não mostra número', async () => {
    mockApi({ unread: 0 });
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    expect(await screen.findByRole('link', { name: 'Notificações' })).toBeInTheDocument();
  });

  it('a caixa monta o texto pelo tipo e destaca os não lidos', async () => {
    mockApi();
    renderWithProviders(<AppRoutes />, { route: '/notificacoes' });

    // O nome acessível também traz o tempo desde o aviso.
    const unread = await screen.findByRole('button', {
      name: /^Novo:\s*@davi_teste propôs alugar “Barraca” de 01\/12\/2026 a 03\/12\/2026\./,
    });
    expect(unread).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: /^Sua proposta para “Furadeira” expirou sem resposta do dono\./,
      }),
    ).toBeInTheDocument();
  });

  it('o clique marca como lido e leva à tela do aviso', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/notificacoes' });

    await user.click(await screen.findByRole('button', { name: /propôs alugar/ }));

    expect(await screen.findByRole('heading', { name: 'Aluguéis' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Meus anúncios' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url === '/api/notifications/n1/read')).toBe(true),
    );
    expect(await screen.findByRole('link', { name: 'Notificações' })).toBeInTheDocument();
  });

  it('aviso já lido não chama a API de novo', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/notificacoes' });

    await user.click(await screen.findByRole('button', { name: /Furadeira/ }));

    expect(await screen.findByRole('tab', { name: 'Histórico' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/read'))).toBe(false);
  });

  it('marcar todos como lidos atualiza a caixa e o sino', async () => {
    const fetchMock = mockApi({ unread: 1 });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/notificacoes' });

    await screen.findByRole('link', { name: 'Notificações, 1 nova' });
    await user.click(await screen.findByRole('button', { name: 'Marcar todos como lidos' }));

    expect(await screen.findByRole('link', { name: 'Notificações' })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Marcar todos como lidos' }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.queryByText('Novo:', { exact: false })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/notifications/read-all')).toBe(true);
  });

  it('caixa vazia', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
      if (url === '/api/notifications/unread-count') return jsonResponse(200, 0);
      if (url.startsWith('/api/notifications?')) return jsonResponse(200, []);
      throw new Error(`URL inesperada: ${url}`);
    });
    renderWithProviders(<AppRoutes />, { route: '/notificacoes' });

    expect(await screen.findByText('Nenhum aviso por enquanto.')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Marcar todos como lidos' }),
    ).not.toBeInTheDocument();
  });
});
