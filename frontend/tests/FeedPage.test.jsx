import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
function listing(id, extra = {}) {
  return {
    id,
    cover_photo: `foto-${id}.jpg`,
    situation: 'available',
    category: 'Ferramentas',
    title: `Item ${id}`,
    daily_price: '15.00',
    neighborhood: 'Centro',
    city: 'Rio Grande',
    created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    is_owner: false,
    is_favorite: false,
    ...extra,
  };
}

function mockApi(feed) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url.startsWith('/api/listings?')) return feed(new URLSearchParams(url.split('?')[1]));
    throw new Error(`URL inesperada: ${url}`);
  });
}

const feedCalls = (fetchMock) =>
  fetchMock.mock.calls
    .map(([url]) => url)
    .filter((url) => url.startsWith('/api/listings?'))
    .map((url) => new URLSearchParams(url.split('?')[1]));

describe('feed (F-15, F-23, F-24)', () => {
  it('mostra os cards com os dados públicos e o contador a partir de total', async () => {
    mockApi(() =>
      jsonResponse(200, {
        items: [
          listing(1, { title: 'Furadeira de impacto', daily_price: '25.00' }),
          listing(2, { title: 'Barraca', situation: 'rented', is_owner: true, cover_photo: null }),
        ],
        next_cursor: null,
        total: 2,
      }),
    );

    renderWithProviders(<AppRoutes />, { route: '/' });

    const card = await screen.findByRole('link', { name: /Furadeira de impacto/ });
    expect(screen.getByText('2 itens encontrados')).toBeInTheDocument();
    expect(card).toHaveAttribute('href', '/itens/1');
    expect(within(card).getByText('Disponível')).toBeInTheDocument();
    expect(within(card).getByText('Ferramentas')).toBeInTheDocument();
    expect(within(card).getByText('R$ 25,00')).toBeInTheDocument();
    expect(within(card).getByText('Centro')).toBeInTheDocument();
    expect(within(card).getByText('há 3 dias')).toBeInTheDocument();
    expect(card.querySelector('img')).toHaveAttribute('src', '/uploads/foto-1.jpg');
    expect(within(card).queryByText('Seu anúncio')).not.toBeInTheDocument();

    const own = screen.getByRole('link', { name: /Barraca/ });
    expect(within(own).getByText('Alugado')).toBeInTheDocument();
    expect(within(own).getByText('Seu anúncio')).toBeInTheDocument();
    expect(within(own).getByText('Sem foto')).toBeInTheDocument();
  });

  it('usa o singular com um item e leva a /anunciar', async () => {
    mockApi(() => jsonResponse(200, { items: [listing(1)], next_cursor: null, total: 1 }));

    renderWithProviders(<AppRoutes />, { route: '/' });

    expect(await screen.findByText('1 item encontrado')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Anunciar item' })).toHaveAttribute(
      'href',
      '/anunciar',
    );
  });

  it('carrega a próxima página pelo cursor quando o fim da lista aparece (RN-30)', async () => {
    const fetchMock = mockApi((params) =>
      params.get('cursor') === 'c2'
        ? jsonResponse(200, { items: [listing(3)], next_cursor: null, total: 3 })
        : jsonResponse(200, { items: [listing(1), listing(2)], next_cursor: 'c2', total: 3 }),
    );

    renderWithProviders(<AppRoutes />, { route: '/' });

    await screen.findByRole('link', { name: /Item 2/ });
    expect(screen.getByRole('button', { name: 'Carregar mais' })).toBeInTheDocument();

    act(() => globalThis.intersectAll());

    expect(await screen.findByRole('link', { name: /Item 3/ })).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument();
    expect(feedCalls(fetchMock).map((params) => params.get('cursor'))).toEqual([null, 'c2']);
  });

  it('o botão "Carregar mais" também busca a próxima página', async () => {
    mockApi((params) =>
      params.get('cursor')
        ? jsonResponse(200, { items: [listing(2)], next_cursor: null, total: 2 })
        : jsonResponse(200, { items: [listing(1)], next_cursor: 'c2', total: 2 }),
    );
    const user = userEvent.setup();

    renderWithProviders(<AppRoutes />, { route: '/' });

    await user.click(await screen.findByRole('button', { name: 'Carregar mais' }));

    expect(await screen.findByRole('link', { name: /Item 2/ })).toBeInTheDocument();
  });

  it('envia à API os filtros que estão na URL', async () => {
    const fetchMock = mockApi(() => jsonResponse(200, { items: [], next_cursor: null, total: 0 }));

    renderWithProviders(<AppRoutes />, {
      route: '/?q=furadeira&categories=2&categories=1&favorites=true',
    });

    expect(await screen.findByText('0 itens encontrados')).toBeInTheDocument();
    expect(screen.getByText('Nenhum item encontrado.')).toBeInTheDocument();
    const [params] = feedCalls(fetchMock);
    expect(params.get('q')).toBe('furadeira');
    expect(params.getAll('categories[]')).toEqual(['1', '2']);
    expect(params.get('favorites')).toBe('true');
  });

  it('erro ao carregar mostra mensagem e permite tentar de novo', async () => {
    let fail = true;
    mockApi(() =>
      fail
        ? jsonResponse(500, { error: { code: 'INTERNAL_ERROR', message: 'Erro no servidor.' } })
        : jsonResponse(200, { items: [listing(1)], next_cursor: null, total: 1 }),
    );
    const user = userEvent.setup();

    renderWithProviders(<AppRoutes />, { route: '/' });

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível carregar os itens.');
    expect(alert).toHaveTextContent('Erro no servidor.');

    fail = false;
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' }));

    expect(await screen.findByRole('link', { name: /Item 1/ })).toBeInTheDocument();
  });

  it('erro na próxima página mantém os itens e oferece tentar de novo', async () => {
    let fail = true;
    mockApi((params) => {
      if (!params.get('cursor')) {
        return jsonResponse(200, { items: [listing(1)], next_cursor: 'c2', total: 2 });
      }
      return fail
        ? jsonResponse(400, { error: { code: 'INVALID_CURSOR', message: 'Cursor inválido.' } })
        : jsonResponse(200, { items: [listing(2)], next_cursor: null, total: 2 });
    });
    const user = userEvent.setup();

    renderWithProviders(<AppRoutes />, { route: '/' });

    await user.click(await screen.findByRole('button', { name: 'Carregar mais' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Cursor inválido.');
    expect(screen.getByRole('link', { name: /Item 1/ })).toBeInTheDocument();

    fail = false;
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' }));

    expect(await screen.findByRole('link', { name: /Item 2/ })).toBeInTheDocument();
  });
});
