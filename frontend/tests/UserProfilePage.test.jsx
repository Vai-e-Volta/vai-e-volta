import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

function mockApi(profileResponse) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 'u1', username: 'ana_teste' });
    if (url.startsWith('/api/users/')) return profileResponse();
    throw new Error(`URL inesperada: ${url}`);
  });
}

describe('perfil público (F-10)', () => {
  it('mostra usuário, bairro e cidade, membro desde e anúncios ativos', async () => {
    const fetchMock = mockApi(() =>
      jsonResponse(200, {
        username: 'bruno.teste',
        neighborhood: 'Cassino',
        city: 'Rio Grande',
        created_at: '2026-10-10T12:00:00Z',
        listings: [
          { id: 'l1', title: 'Furadeira de impacto', daily_price: '25.00' },
          { id: 'l2', title: 'Barraca para 4 pessoas', daily_price: '45.50' },
        ],
      }),
    );

    renderWithProviders(<AppRoutes />, { route: '/usuarios/bruno.teste' });

    expect(await screen.findByRole('heading', { name: '@bruno.teste' })).toBeInTheDocument();
    expect(screen.getByText('Cassino, Rio Grande')).toBeInTheDocument();
    expect(screen.getByText('10/10/2026')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Anúncios ativos (2)' })).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /Furadeira de impacto/ });
    expect(link).toHaveAttribute('href', '/itens/l1');
    expect(within(link).getByText(/R\$ 25,00/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/users/bruno.teste')).toBe(true);
  });

  it('sem anúncios ativos mostra mensagem clara', async () => {
    mockApi(() =>
      jsonResponse(200, {
        username: 'bruno.teste',
        neighborhood: 'Cassino',
        city: 'Rio Grande',
        created_at: '2026-10-10T12:00:00Z',
        listings: [],
      }),
    );

    renderWithProviders(<AppRoutes />, { route: '/usuarios/bruno.teste' });

    expect(await screen.findByText('Nenhum anúncio ativo no momento.')).toBeInTheDocument();
  });

  it('usuário inexistente ou excluído (404) mostra perfil não encontrado', async () => {
    const fetchMock = mockApi(() =>
      jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Usuário não encontrado.' } }),
    );

    renderWithProviders(<AppRoutes />, { route: '/usuarios/ninguem' });

    expect(
      await screen.findByRole('heading', { name: 'Perfil não encontrado' }),
    ).toBeInTheDocument();
    // 404 não é repetido.
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/users/ninguem')).toHaveLength(1);
  });
});
