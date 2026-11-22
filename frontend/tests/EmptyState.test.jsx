import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

function mockApi() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/categories' || url.startsWith('/api/tags')) return jsonResponse(200, []);
    if (url === '/api/listings/price-ranges') return jsonResponse(200, { ranges: [] });
    if (url.startsWith('/api/listings?')) {
      return jsonResponse(200, { items: [], next_cursor: null, total: 0 });
    }
    throw new Error(`URL inesperada: ${url}`);
  });
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="search">{location.search}</output>;
}

function renderFeed(route) {
  renderWithProviders(
    <>
      <AppRoutes />
      <LocationProbe />
    </>,
    { route },
  );
  return screen.findByRole('heading', { name: 'Nenhum item encontrado' });
}

describe('feed vazio (F-27)', () => {
  it('sem filtros, explica e leva a anunciar, sem botão de limpar', async () => {
    mockApi();
    await renderFeed('/');

    expect(screen.getByText(/Ainda não há itens para alugar/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Limpar filtros' })).not.toBeInTheDocument();
    const links = screen.getAllByRole('link', { name: 'Anunciar item' });
    expect(links.every((link) => link.getAttribute('href') === '/anunciar')).toBe(true);
  });

  it('com filtros, "Limpar filtros" zera a URL e consulta o feed sem eles', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    await renderFeed('/?q=xyz&categories=2&sort=price_asc');

    expect(screen.getByText(/Nenhum anúncio combina com a busca/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Limpar filtros' }));

    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
    expect(screen.getByRole('searchbox', { name: 'Buscar pelo nome do item' })).toHaveValue('');
    await vi.waitFor(() => {
      const urls = fetchMock.mock.calls
        .map(([url]) => url)
        .filter((url) => url.startsWith('/api/listings?'));
      expect(urls.at(-1)).toBe('/api/listings?limit=20');
    });
  });

  it('só a ordenação não conta como filtro', async () => {
    mockApi();
    await renderFeed('/?sort=oldest');

    expect(screen.queryByRole('button', { name: 'Limpar filtros' })).not.toBeInTheDocument();
  });
});
