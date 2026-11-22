import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { parsePriceRange, priceToInput } from '../src/utils/feedFilters';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const POPULAR = [{ name: 'camping' }, { name: 'praia' }, { name: 'furadeira' }];
const RANGES = [
  { label: 'Mais baratos', min: '5.00', max: '15.00' },
  { label: 'Intermediários', min: '15.00', max: '40.00' },
  { label: 'Mais caros', min: '40.00', max: '200.00' },
];

function mockApi({ ranges = RANGES } = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/categories') return jsonResponse(200, []);
    if (url === '/api/tags') return jsonResponse(200, POPULAR);
    if (url.startsWith('/api/tags?')) {
      const q = new URLSearchParams(url.split('?')[1]).get('q');
      return jsonResponse(200, { tags: [{ name: `${q}-grande` }, { name: `mini-${q}` }] });
    }
    if (url === '/api/listings/price-ranges') return jsonResponse(200, { ranges });
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
  renderWithProviders(
    <>
      <AppRoutes />
      <LocationProbe />
    </>,
    { route },
  );
  return screen.findByRole('complementary', { name: 'Filtros' });
}

describe('faixa de preço digitada (F-18)', () => {
  it('aceita campos vazios, inteiros e vírgula', () => {
    expect(parsePriceRange('', '')).toEqual({
      values: { price_min: null, price_max: null },
      errors: {},
    });
    expect(parsePriceRange('10', 'R$ 25,5').values).toEqual({
      price_min: '10.00',
      price_max: '25.50',
    });
  });

  it('aponta valor inválido e mínimo maior que o máximo', () => {
    expect(parsePriceRange('abc', '').errors).toEqual({
      price_min: 'Use um valor como 25 ou 25,50.',
    });
    expect(parsePriceRange('30', '20').errors).toEqual({
      price_max: 'O máximo não pode ser menor que o mínimo.',
    });
  });

  it('mostra o valor da URL com vírgula', () => {
    expect(priceToInput('12.50')).toBe('12,50');
    expect(priceToInput('')).toBe('');
  });
});

describe('tags (F-17, RN-26)', () => {
  it('mostra as mais usadas e combina as marcadas com OU', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed();
    const group = within(sidebar).getByRole('group', { name: 'Tags' });

    expect(within(group).getByText('Mais usadas')).toBeInTheDocument();
    await user.click(await within(group).findByRole('button', { name: 'praia' }));
    await user.click(within(group).getByRole('button', { name: 'camping' }));

    expect(within(group).getByRole('button', { name: 'praia' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByTestId('search')).toHaveTextContent('?tags=praia&tags=camping');
    await vi.waitFor(() =>
      expect(lastFeedCall(fetchMock).getAll('tags[]')).toEqual(['camping', 'praia']),
    );
  });

  it('busca outras tags e mantém visíveis as marcadas fora da lista', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed('/?tags=praia');
    const group = within(sidebar).getByRole('group', { name: 'Tags' });

    await user.type(within(group).getByRole('searchbox', { name: 'Buscar tag' }), 'barraca');

    await user.click(await within(group).findByRole('button', { name: 'barraca-grande' }));
    expect(within(group).getByText('Tags com “barraca”')).toBeInTheDocument();
    expect(within(group).getByRole('button', { name: 'praia' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/tags?q=barraca')).toBe(true);
    expect(screen.getByTestId('search')).toHaveTextContent('?tags=praia&tags=barraca-grande');

    await user.click(within(group).getByRole('button', { name: 'Limpar tags' }));
    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
  });
});

describe('preço (F-18, F-19)', () => {
  it('aplica mínimo e máximo digitados', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed();
    const group = within(sidebar).getByRole('group', { name: 'Preço por dia' });

    await user.type(within(group).getByLabelText('Mínimo'), '10');
    await user.type(within(group).getByLabelText('Máximo'), '25,50');
    await user.click(within(group).getByRole('button', { name: 'Aplicar preço' }));

    expect(screen.getByTestId('search')).toHaveTextContent('?price_min=10.00&price_max=25.50');
    await vi.waitFor(() => {
      const params = lastFeedCall(fetchMock);
      expect(params.get('price_min')).toBe('10.00');
      expect(params.get('price_max')).toBe('25.50');
    });
  });

  it('não aplica faixa inválida e mostra o erro no campo', async () => {
    mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed();
    const group = within(sidebar).getByRole('group', { name: 'Preço por dia' });

    await user.type(within(group).getByLabelText('Mínimo'), '50');
    await user.type(within(group).getByLabelText('Máximo'), '20');
    await user.click(within(group).getByRole('button', { name: 'Aplicar preço' }));

    expect(within(group).getByLabelText('Máximo')).toHaveAttribute('aria-invalid', 'true');
    expect(
      within(group).getByText('O máximo não pode ser menor que o mínimo.'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
  });

  it('atalhos de faixa preenchem o preço e desmarcam no segundo clique', async () => {
    mockApi();
    const user = userEvent.setup();
    const sidebar = await renderFeed();
    const group = within(sidebar).getByRole('group', { name: 'Preço por dia' });

    const shortcut = await within(group).findByRole('button', { name: /Intermediários/ });
    await user.click(shortcut);

    expect(shortcut).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('search')).toHaveTextContent('?price_min=15.00&price_max=40.00');
    expect(within(group).getByLabelText('Mínimo')).toHaveValue('15,00');
    expect(screen.getByRole('button', { name: 'Filtros (1)' })).toBeInTheDocument();

    await user.click(shortcut);

    expect(screen.getByTestId('search')).toHaveTextContent(/^$/);
    expect(within(group).getByLabelText('Mínimo')).toHaveValue('');
  });

  it('sem atalhos da API (menos de 3 anúncios), só os campos aparecem', async () => {
    mockApi({ ranges: [] });
    const sidebar = await renderFeed('/?price_min=5.00');
    const group = within(sidebar).getByRole('group', { name: 'Preço por dia' });

    expect(within(group).getByLabelText('Mínimo')).toHaveValue('5,00');
    expect(within(group).queryByRole('button', { name: /Mais baratos/ })).not.toBeInTheDocument();
    expect(within(group).getByRole('button', { name: 'Limpar preço por dia' })).toBeInTheDocument();
  });
});
