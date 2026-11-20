import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios. O relógio fica em 20/11/2026 para as regras de "hoje".
const LISTING = {
  id: 7,
  title: 'Barraca para 4 pessoas',
  description: 'Com sobreteto.',
  daily_price: '15.00',
  max_days: 5,
  available_from: '2026-12-01',
  available_until: '2026-12-31',
  category: { id: 2, name: 'Camping' },
  tags: [],
  photos: [],
  pickup_street: 'Rua Exemplo',
  pickup_neighborhood: 'Cassino',
  pickup_city: 'Rio Grande',
  owner: { username: 'bruno_teste' },
  status: 'active',
  situation: 'available',
  is_owner: false,
  unavailable: false,
};

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-20T12:00:00-03:00'));
});

afterEach(() => {
  vi.useRealTimers();
});

function mockApi(propose = () => jsonResponse(201, { id: 90, status: 'pending' })) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/listings/7' && method === 'GET') return jsonResponse(200, LISTING);
    if (url === '/api/listings/7/booked-periods') return jsonResponse(200, []);
    if (url === '/api/listings/7/rentals' && method === 'POST') return propose(options);
    throw new Error(`URL inesperada: ${method} ${url}`);
  });
}

async function openPanel() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/itens/7' });
  await user.click(await screen.findByRole('button', { name: 'Propor aluguel' }));
  const panel = screen.getByRole('region', { name: 'Propor aluguel' });
  return { user, panel };
}

async function fillPeriod(user, panel, start, end) {
  await user.type(within(panel).getByLabelText('Início'), start);
  await user.type(within(panel).getByLabelText('Fim'), end);
}

describe('propor aluguel (F-30, F-32 a F-34)', () => {
  it('abre a escolha de período com foco no início e mostra o resumo', async () => {
    mockApi();
    const { user, panel } = await openPanel();

    expect(within(panel).getByLabelText('Início')).toHaveFocus();
    expect(
      within(panel).getByText('Escolha as datas para ver o total estimado.'),
    ).toBeInTheDocument();

    await fillPeriod(user, panel, '01122026', '03122026');

    expect(within(panel).getByLabelText('Início')).toHaveValue('01/12/2026');
    expect(within(panel).getByText('3 dias · R$ 45,00')).toBeInTheDocument();
  });

  it('envia o período no formato da API e confirma o envio', async () => {
    const fetchMock = mockApi();
    const { user, panel } = await openPanel();

    await fillPeriod(user, panel, '01/12/2026', '01/12/2026');
    expect(within(panel).getByText('1 dia · R$ 15,00')).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: 'Enviar proposta' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Proposta enviada!');
    const [, options] = fetchMock.mock.calls.find(([url]) => url === '/api/listings/7/rentals');
    expect(JSON.parse(options.body)).toEqual({ start_date: '2026-12-01', end_date: '2026-12-01' });
    expect(screen.queryByRole('region', { name: 'Propor aluguel' })).not.toBeInTheDocument();
  });

  it('não envia período que a tela já sabe que é inválido', async () => {
    const fetchMock = mockApi();
    const { user, panel } = await openPanel();

    await fillPeriod(user, panel, '01/12/2026', '10/12/2026');
    await user.click(within(panel).getByRole('button', { name: 'Enviar proposta' }));

    expect(within(panel).getByLabelText('Fim')).toHaveAttribute('aria-invalid', 'true');
    expect(
      within(panel).getByText('Este item é alugado por no máximo 5 dias.'),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/listings/7/rentals')).toBe(false);
  });

  it.each([
    ['RENTAL_OVERLAP', 409, 'Esse período já está reservado para outro aluguel.'],
    ['DUPLICATE_PROPOSAL', 409, 'Você já tem uma proposta pendente para este item'],
    ['LISTING_UNAVAILABLE', 409, 'Este anúncio não está mais disponível para propostas.'],
    ['FORBIDDEN', 403, 'Você não pode alugar o próprio item.'],
  ])('%s vira uma mensagem clara', async (code, status, text) => {
    mockApi(() => jsonResponse(status, { error: { code, message: 'Recusado.' } }));
    const { user, panel } = await openPanel();

    await fillPeriod(user, panel, '01/12/2026', '02/12/2026');
    await user.click(within(panel).getByRole('button', { name: 'Enviar proposta' }));

    expect(await within(panel).findByRole('alert')).toHaveTextContent(text);
  });

  it('DUPLICATE_PROPOSAL leva aos aluguéis', async () => {
    mockApi(() =>
      jsonResponse(409, { error: { code: 'DUPLICATE_PROPOSAL', message: 'Duplicada.' } }),
    );
    const { user, panel } = await openPanel();

    await fillPeriod(user, panel, '01/12/2026', '02/12/2026');
    await user.click(within(panel).getByRole('button', { name: 'Enviar proposta' }));

    const alert = await within(panel).findByRole('alert');
    expect(within(alert).getByRole('link', { name: 'Ver meus aluguéis' })).toHaveAttribute(
      'href',
      '/alugueis',
    );
  });

  it('422 marca os campos indicados pela API', async () => {
    mockApi(() =>
      jsonResponse(422, {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Revise o período.',
          fields: { start_date: 'Fora da janela do anúncio.' },
        },
      }),
    );
    const { user, panel } = await openPanel();

    await fillPeriod(user, panel, '01/12/2026', '02/12/2026');
    await user.click(within(panel).getByRole('button', { name: 'Enviar proposta' }));

    expect(await within(panel).findByText('Fora da janela do anúncio.')).toBeInTheDocument();
    expect(within(panel).getByLabelText('Início')).toHaveAttribute('aria-invalid', 'true');
    expect(within(panel).getByRole('alert')).toHaveTextContent('Revise o período.');
  });

  it('Cancelar fecha sem enviar', async () => {
    const fetchMock = mockApi();
    const { user, panel } = await openPanel();

    await user.click(within(panel).getByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByRole('region', { name: 'Propor aluguel' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Propor aluguel' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/listings/7/rentals')).toBe(false);
  });
});
