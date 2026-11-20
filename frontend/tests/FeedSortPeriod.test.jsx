import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { parsePeriod } from '../src/utils/feedFilters';
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

async function renderFeed(route = '/') {
  renderWithProviders(
    <>
      <AppRoutes />
      <LocationProbe />
    </>,
    { route },
  );
  return screen.findByRole('complementary', { name: 'Filtros' });
}

describe('período desejado (F-22, RN-29)', () => {
  it('sem datas não filtra; com as duas, vale o período no formato da API', () => {
    expect(parsePeriod('', '')).toEqual({
      values: { needed_from: null, needed_until: null },
      errors: {},
    });
    expect(parsePeriod('01/12/2026', ' 03/12/2026 ')).toEqual({
      values: { needed_from: '2026-12-01', needed_until: '2026-12-03' },
      errors: {},
    });
  });

  it('exige as duas datas, datas que existem e o fim depois do início', () => {
    expect(parsePeriod('01/12/2026', '').errors).toEqual({
      needed_until: 'Informe a data de fim.',
    });
    expect(parsePeriod('', '01/12/2026').errors).toEqual({
      needed_from: 'Informe a data de início.',
    });
    expect(parsePeriod('31/02/2026', '01/3/2026').errors).toEqual({
      needed_from: 'Data inválida. Use dd/mm/aaaa.',
      needed_until: 'Data inválida. Use dd/mm/aaaa.',
    });
    expect(parsePeriod('05/12/2026', '01/12/2026').errors).toEqual({
      needed_until: 'O fim deve ser no mesmo dia ou depois do início.',
    });
  });
});

describe('ordenação (F-20)', () => {
  it('troca a ordem e volta ao padrão sem deixar sort na URL', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    await renderFeed();

    const select = screen.getByRole('combobox', { name: 'Ordenar por' });
    expect(select).toHaveValue('newest');

    await user.selectOptions(select, 'Menor preço');
    expect(screen.getByTestId('search')).toHaveTextContent('?sort=price_asc');
    await vi.waitFor(() => expect(lastFeedCall(fetchMock).get('sort')).toBe('price_asc'));

    await user.selectOptions(select, 'Mais recentes');
    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
  });

  it('a ordem da URL vem selecionada e não conta como filtro da lateral', async () => {
    mockApi();
    await renderFeed('/?sort=oldest');

    expect(screen.getByRole('combobox', { name: 'Ordenar por' })).toHaveValue('oldest');
    expect(screen.getByRole('button', { name: 'Filtros' })).toBeInTheDocument();
  });
});

describe('disponibilidade (F-21, RN-28)', () => {
  it('filtra por disponíveis agora e "Todos" tira o filtro', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed();
    const group = within(sidebar).getByRole('group', { name: 'Disponibilidade' });

    expect(within(group).getByRole('radio', { name: 'Todos' })).toBeChecked();
    await user.click(within(group).getByRole('radio', { name: 'Disponíveis agora' }));

    expect(screen.getByTestId('search')).toHaveTextContent('?availability=available_now');
    await vi.waitFor(() =>
      expect(lastFeedCall(fetchMock).get('availability')).toBe('available_now'),
    );

    await user.click(within(group).getByRole('radio', { name: 'Todos' }));
    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
  });
});

describe('período na lateral (F-22)', () => {
  it('aplica o período com as duas datas no formato da API', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed();
    const group = within(sidebar).getByRole('group', { name: 'Período' });

    await user.type(within(group).getByLabelText('Preciso de'), '01122099');
    await user.type(within(group).getByLabelText('até'), '03122099');
    expect(within(group).getByLabelText('Preciso de')).toHaveValue('01/12/2099');
    await user.click(within(group).getByRole('button', { name: 'Aplicar período' }));

    expect(screen.getByTestId('search')).toHaveTextContent(
      '?needed_from=2099-12-01&needed_until=2099-12-03',
    );
    await vi.waitFor(() => {
      const params = lastFeedCall(fetchMock);
      expect(params.get('needed_from')).toBe('2099-12-01');
      expect(params.get('needed_until')).toBe('2099-12-03');
    });
    expect(screen.getByRole('button', { name: 'Filtros (1)' })).toBeInTheDocument();
  });

  it('com uma data só, mostra o erro e não aplica', async () => {
    mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed();
    const group = within(sidebar).getByRole('group', { name: 'Período' });

    await user.type(within(group).getByLabelText('Preciso de'), '01/12/2099');
    await user.click(within(group).getByRole('button', { name: 'Aplicar período' }));

    expect(within(group).getByLabelText('até')).toHaveAttribute('aria-invalid', 'true');
    expect(within(group).getByText('Informe a data de fim.')).toBeInTheDocument();
    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
  });

  it('período da URL aparece nos campos e "Limpar" remove as duas datas', async () => {
    mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed('/?needed_from=2099-12-01&needed_until=2099-12-03&q=x');
    const group = within(sidebar).getByRole('group', { name: 'Período' });

    expect(within(group).getByLabelText('Preciso de')).toHaveValue('01/12/2099');
    await user.click(within(group).getByRole('button', { name: 'Limpar período' }));

    expect(screen.getByTestId('search')).toHaveTextContent('?q=x');
    expect(within(group).getByLabelText('Preciso de')).toHaveValue('');
  });
});
