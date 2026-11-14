import { screen } from '@testing-library/react';
import { useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

const loggedUser = { id: 'u1', username: 'ana_teste' };

function mockSession(user) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') {
      return user
        ? jsonResponse(200, user)
        : jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Faça login.' } });
    }
    return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Não encontrado.' } });
  });
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="from">{location.state?.from?.pathname ?? ''}</output>;
}

describe('mapa de rotas', () => {
  it('rota privada sem sessão leva a /login guardando o destino', async () => {
    mockSession(null);

    renderWithProviders(
      <>
        <AppRoutes />
        <LocationProbe />
      </>,
      { route: '/alugueis' },
    );

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByTestId('from')).toHaveTextContent('/alugueis');
  });

  it('rota privada com sessão mostra a tela', async () => {
    mockSession(loggedUser);

    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    expect(await screen.findByRole('heading', { name: 'Aluguéis' })).toBeInTheDocument();
  });

  it.each(['/login', '/cadastro'])('%s com sessão redireciona a /', async (route) => {
    mockSession(loggedUser);

    renderWithProviders(<AppRoutes />, { route });

    expect(await screen.findByRole('heading', { name: 'Itens para alugar' })).toBeInTheDocument();
  });

  it('/cadastro é pública', async () => {
    mockSession(null);

    renderWithProviders(<AppRoutes />, { route: '/cadastro' });

    expect(await screen.findByRole('heading', { name: 'Criar conta' })).toBeInTheDocument();
  });

  it('rota desconhecida mostra a página 404', async () => {
    mockSession(null);

    renderWithProviders(<AppRoutes />, { route: '/nao-existe' });

    expect(
      await screen.findByRole('heading', { name: 'Página não encontrada' }),
    ).toBeInTheDocument();
  });

  it.each([
    ['/itens/1', 'Item'],
    ['/anunciar', 'Anunciar item'],
    ['/anuncios/1/editar', 'Editar anúncio'],
    ['/usuarios/ana_teste', 'Perfil'],
    ['/configuracoes', 'Configurações'],
    ['/notificacoes', 'Notificações'],
  ])('rota privada %s existe', async (route, heading) => {
    mockSession(loggedUser);

    renderWithProviders(<AppRoutes />, { route });

    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
  });
});
