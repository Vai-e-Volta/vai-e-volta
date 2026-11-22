import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
function listing(id, extra = {}) {
  return {
    id,
    cover_photo: null,
    situation: 'available',
    category: 'Camping',
    title: `Item ${id}`,
    daily_price: '20.00',
    neighborhood: 'Centro',
    city: 'Rio Grande',
    created_at: '2026-11-01T12:00:00Z',
    is_owner: false,
    is_favorite: false,
    ...extra,
  };
}

/** API fictícia com os favoritos guardados em memória. */
function mockApi({ failFavorite = false, delayFavorite = null } = {}) {
  const favorites = new Set([2]);
  const items = [listing(1), listing(2), listing(3, { is_owner: true })];
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/categories' || url.startsWith('/api/tags')) return jsonResponse(200, []);
    if (url === '/api/listings/price-ranges') return jsonResponse(200, { ranges: [] });
    const favoriteMatch = /^\/api\/listings\/(\d+)\/favorite$/.exec(url);
    if (favoriteMatch) {
      if (delayFavorite) await delayFavorite;
      if (failFavorite) {
        return jsonResponse(404, {
          error: { code: 'LISTING_NOT_FOUND', message: 'Anúncio não encontrado.' },
        });
      }
      const id = Number(favoriteMatch[1]);
      if (options.method === 'PUT') favorites.add(id);
      else favorites.delete(id);
      return new Response(null, { status: 204 });
    }
    if (url.startsWith('/api/listings?')) {
      const onlyFavorites = new URLSearchParams(url.split('?')[1]).get('favorites') === 'true';
      const page = items
        .map((item) => ({ ...item, is_favorite: favorites.has(item.id) }))
        .filter((item) => !onlyFavorites || item.is_favorite);
      return jsonResponse(200, { items: page, next_cursor: null, total: page.length });
    }
    throw new Error(`URL inesperada: ${url}`);
  });
  return { fetchMock, favorites };
}

const heart = (name) => screen.getByRole('button', { name: `Favoritar ${name}` });

describe('favoritos (F-26)', () => {
  it('o coração mostra o estado e favorita com PUT', async () => {
    const { fetchMock, favorites } = mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/' });

    await screen.findByRole('article', { name: 'Item 1' });
    expect(heart('Item 2')).toHaveAttribute('aria-pressed', 'true');

    await user.click(heart('Item 1'));

    expect(heart('Item 1')).toHaveAttribute('aria-pressed', 'true');
    expect(favorites.has(1)).toBe(true);
    expect(
      fetchMock.mock.calls.some(
        ([url, options]) => url === '/api/listings/1/favorite' && options.method === 'PUT',
      ),
    ).toBe(true);
  });

  it('muda na hora, antes da resposta da API (ação otimista)', async () => {
    let release;
    const { favorites } = mockApi({ delayFavorite: new Promise((resolve) => (release = resolve)) });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/' });

    await screen.findByRole('article', { name: 'Item 2' });
    await user.click(heart('Item 2'));

    expect(heart('Item 2')).toHaveAttribute('aria-pressed', 'false');
    expect(favorites.has(2)).toBe(true);

    release();
    await vi.waitFor(() => expect(favorites.has(2)).toBe(false));
    expect(heart('Item 2')).toHaveAttribute('aria-pressed', 'false');
  });

  it('se a API recusar, o coração volta e aparece o aviso', async () => {
    mockApi({ failFavorite: true });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/' });

    await screen.findByRole('article', { name: 'Item 1' });
    await user.click(heart('Item 1'));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível atualizar o favorito. Anúncio não encontrado.',
    );
    expect(heart('Item 1')).toHaveAttribute('aria-pressed', 'false');
  });

  it('o filtro "Favoritos" mostra só os favoritos e reflete o desfavoritar', async () => {
    mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/' });

    const sidebar = await screen.findByRole('complementary', { name: 'Filtros' });
    await user.click(within(sidebar).getByRole('checkbox', { name: 'Só meus favoritos' }));

    await vi.waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));
    expect(screen.getByText('1 item encontrado')).toBeInTheDocument();

    await user.click(heart('Item 2'));

    expect(
      await screen.findByRole('heading', { name: 'Nenhum item encontrado' }),
    ).toBeInTheDocument();
  });
});
