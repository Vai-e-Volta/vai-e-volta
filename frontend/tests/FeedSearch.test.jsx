import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { useFeedFilters } from '../src/hooks/useFeedFilters';
import { applyFilterChanges } from '../src/utils/feedFilters';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const CATEGORIES = [
  { id: 1, name: 'Ferramentas' },
  { id: 2, name: 'Camping' },
  { id: 3, name: 'Eletrônicos' },
];

function mockApi() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/categories') return jsonResponse(200, CATEGORIES);
    if (url.startsWith('/api/tags')) return jsonResponse(200, []);
    if (url === '/api/listings/price-ranges') return jsonResponse(200, { ranges: [] });
    if (url.startsWith('/api/listings?')) {
      return jsonResponse(200, { items: [], next_cursor: null, total: 0 });
    }
    throw new Error(`URL inesperada: ${url}`);
  });
}

const lastFeedCall = (fetchMock) => {
  const urls = fetchMock.mock.calls
    .map(([url]) => url)
    .filter((url) => url.startsWith('/api/listings?'));
  return new URLSearchParams(urls.at(-1).split('?')[1]);
};

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="search">{location.search}</output>;
}

function renderFeed(route = '/') {
  return renderWithProviders(
    <>
      <AppRoutes />
      <LocationProbe />
    </>,
    { route },
  );
}

describe('applyFilterChanges', () => {
  it('troca só as chaves informadas e remove valores vazios', () => {
    const current = new URLSearchParams('q=barraca&categories=1&sort=newest');

    expect(
      applyFilterChanges(current, { q: ' furadeira ', categories: ['2', '3'] }).toString(),
    ).toBe('sort=newest&q=furadeira&categories=2&categories=3');
    expect(applyFilterChanges(current, { q: '', categories: [] }).toString()).toBe('sort=newest');
  });
});

describe('useFeedFilters', () => {
  it('duas mudanças antes de a tela atualizar não se apagam', async () => {
    function Probe() {
      const { setFilters } = useFeedFilters();
      return (
        <>
          <button
            type="button"
            onClick={() => {
              setFilters({ categories: ['2'] });
              setFilters({ q: 'ca' }, { replace: true });
            }}
          >
            Mudar
          </button>
          <LocationProbe />
        </>
      );
    }
    render(
      <MemoryRouter initialEntries={['/?sort=newest']}>
        <Probe />
      </MemoryRouter>,
    );

    await userEvent.setup().click(screen.getByRole('button', { name: 'Mudar' }));

    expect(screen.getByTestId('search')).toHaveTextContent('?sort=newest&categories=2&q=ca');
  });
});

describe('busca pelo nome (F-16)', () => {
  it('consulta depois de uma espera curta e guarda a busca na URL', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderFeed();

    const field = await screen.findByRole('searchbox', { name: 'Buscar pelo nome do item' });
    await user.type(field, 'furadeira');

    // Antes da espera, nada de consulta a cada letra.
    expect(lastFeedCall(fetchMock).get('q')).toBeNull();
    await vi.waitFor(() => expect(screen.getByTestId('search')).toHaveTextContent('?q=furadeira'), {
      timeout: 2000,
    });
    await vi.waitFor(() => expect(lastFeedCall(fetchMock).get('q')).toBe('furadeira'));
    expect(fetchMock.mock.calls.filter(([url]) => url.startsWith('/api/listings?'))).toHaveLength(
      2,
    );
  });

  it('Enter busca na hora', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderFeed();

    await user.type(
      await screen.findByRole('searchbox', { name: 'Buscar pelo nome do item' }),
      'barraca{Enter}',
    );

    await vi.waitFor(() => expect(lastFeedCall(fetchMock).get('q')).toBe('barraca'));
  });

  it('a busca vinda da URL aparece no campo e vai à API', async () => {
    const fetchMock = mockApi();
    renderFeed('/?q=projetor');

    expect(await screen.findByRole('searchbox', { name: 'Buscar pelo nome do item' })).toHaveValue(
      'projetor',
    );
    await vi.waitFor(() => expect(lastFeedCall(fetchMock).get('q')).toBe('projetor'));
  });

  it('apagar a busca remove o filtro da URL', async () => {
    mockApi();
    const user = userEvent.setup();
    renderFeed('/?q=projetor');

    await user.clear(await screen.findByRole('searchbox', { name: 'Buscar pelo nome do item' }));
    await user.keyboard('{Enter}');

    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
  });
});

describe('categorias na lateral (F-25, RN-26)', () => {
  it('lista as categorias fixas e combina as marcadas com OU', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderFeed();

    const sidebar = await screen.findByRole('complementary', { name: 'Filtros' });
    const group = within(sidebar).getByRole('group', { name: 'Categorias' });
    await user.click(await within(group).findByRole('checkbox', { name: 'Camping' }));
    await user.click(within(group).getByRole('checkbox', { name: 'Ferramentas' }));

    expect(screen.getByTestId('search')).toHaveTextContent('?categories=2&categories=1');
    await vi.waitFor(() =>
      expect(lastFeedCall(fetchMock).getAll('categories[]')).toEqual(['1', '2']),
    );
    expect(within(group).getByRole('checkbox', { name: 'Camping' })).toBeChecked();
  });

  it('categorias da URL vêm marcadas e "Limpar" desmarca todas', async () => {
    mockApi();
    const user = userEvent.setup();
    renderFeed('/?categories=3&q=tv');

    const box = await screen.findByRole('checkbox', { name: 'Eletrônicos' });
    expect(box).toBeChecked();

    await user.click(screen.getByRole('button', { name: 'Limpar categorias' }));

    expect(box).not.toBeChecked();
    expect(screen.getByTestId('search')).toHaveTextContent('?q=tv');
  });

  it('no celular, os filtros abrem por um botão que mostra quantos estão em uso', async () => {
    mockApi();
    const user = userEvent.setup();
    renderFeed('/?categories=1&categories=2');

    const toggle = await screen.findByRole('button', { name: 'Filtros (2)' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(document.getElementById(toggle.getAttribute('aria-controls'))).toHaveClass('block');
  });
});

describe('troca de filtro', () => {
  it('mantém a lista anterior enquanto a nova consulta chega', async () => {
    let resolveSecond;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
      if (url === '/api/categories') return jsonResponse(200, CATEGORIES);
      if (url.startsWith('/api/tags')) return jsonResponse(200, []);
      if (url === '/api/listings/price-ranges') return jsonResponse(200, { ranges: [] });
      if (url.includes('categories')) {
        return new Promise((resolve) => {
          resolveSecond = () =>
            resolve(jsonResponse(200, { items: [], next_cursor: null, total: 0 }));
        });
      }
      return jsonResponse(200, {
        items: [
          {
            id: 1,
            cover_photo: null,
            situation: 'available',
            category: 'Ferramentas',
            title: 'Furadeira',
            daily_price: '10.00',
            neighborhood: 'Centro',
            city: 'Rio Grande',
            created_at: '2026-11-01T12:00:00Z',
            is_owner: false,
            is_favorite: false,
          },
        ],
        next_cursor: null,
        total: 1,
      });
    });
    const user = userEvent.setup();
    renderFeed();

    await user.click(await screen.findByRole('checkbox', { name: 'Camping' }));

    expect(screen.getByRole('link', { name: /Furadeira/ })).toBeInTheDocument();
    await act(async () => resolveSecond());
    expect(await screen.findByText('Nenhum item encontrado.')).toBeInTheDocument();
  });
});
