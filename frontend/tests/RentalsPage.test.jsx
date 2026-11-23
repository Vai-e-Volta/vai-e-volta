import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios. O relógio fica em 20/11/2026.
const listing = (id, title) => ({ id, title, cover_photo: null });

const RENTER_ACTIVE = [
  {
    id: 'r1',
    status: 'pending',
    situation: 'Aguardando',
    start_date: '2026-12-01',
    end_date: '2026-12-03',
    estimated_total: '45.00',
    listing: listing(7, 'Barraca para 4 pessoas'),
    owner: { username: 'bruno_teste' },
  },
  {
    id: 'r2',
    status: 'accepted',
    situation: 'Reservado',
    start_date: '2026-11-21',
    end_date: '2026-11-21',
    estimated_total: '20.00',
    listing: listing(8, 'Furadeira de impacto'),
    owner: { username: 'carla_teste', phone: '(53) 90000-0000' },
  },
  {
    id: 'r3',
    status: 'accepted',
    situation: 'Em andamento',
    start_date: '2026-11-20',
    end_date: '2026-11-22',
    estimated_total: '30.00',
    listing: listing(9, 'Bicicleta aro 29'),
    owner: null,
  },
];

const RENTER_HISTORY = [
  {
    id: 'r4',
    status: 'completed',
    situation: 'Concluído',
    start_date: '2026-10-01',
    end_date: '2026-10-02',
    estimated_total: '30.00',
    listing: listing(10, 'Projetor Full HD'),
    owner: { username: 'bruno_teste' },
  },
];

const OWNER_ACTIVE = [
  {
    id: 'o1',
    status: 'accepted',
    situation: 'Atrasado',
    start_date: '2026-11-10',
    end_date: '2026-11-12',
    estimated_total: '45.00',
    listing: listing(11, 'Caixa de som'),
    renter: { username: 'davi_teste', phone: '(53) 91111-1111' },
  },
];

const MY_LISTINGS = [
  {
    id: 11,
    title: 'Caixa de som',
    cover_photo: null,
    status: 'paused',
    situation: 'rented',
    daily_price: '15.00',
  },
];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-20T12:00:00-03:00'));
});

afterEach(() => {
  vi.useRealTimers();
});

function mockApi({ cancel } = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url.startsWith('/api/listings?')) return jsonResponse(200, { items: [], total: 0 });
    if (url === '/api/categories' || url.startsWith('/api/tags')) return jsonResponse(200, []);
    if (url === '/api/listings/price-ranges') return jsonResponse(200, { ranges: [] });
    const parsed = new URL(url, 'http://localhost');
    const params = parsed.searchParams;
    if (parsed.pathname === '/api/me/rentals') {
      const role = params.get('role');
      const scope = params.get('scope');
      if (role === 'renter') {
        const items = scope === 'history' ? RENTER_HISTORY : RENTER_ACTIVE;
        return jsonResponse(200, { items, next_cursor: null });
      }
      return jsonResponse(200, {
        items: scope === 'history' ? [] : OWNER_ACTIVE,
        next_cursor: null,
      });
    }
    if (parsed.pathname === '/api/me/listings') {
      const items = params.get('scope') === 'history' ? [] : MY_LISTINGS;
      return jsonResponse(200, { items, next_cursor: null });
    }
    if (url === '/api/rentals/r1/cancel' && method === 'POST') {
      return cancel ? cancel() : jsonResponse(200, { id: 'r1', status: 'canceled' });
    }
    throw new Error(`URL inesperada: ${method} ${url}`);
  });
}

const card = (name) => screen.findByRole('article', { name: new RegExp(`^${name}`) });

describe('tela Aluguéis (F-42, F-43, F-45)', () => {
  it('permite acessar meus anúncios pelo feed e ver os controles', async () => {
    mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/' });
    await user.click(await screen.findByRole('link', { name: 'Meus anúncios' }));
    expect(await screen.findByRole('tab', { name: 'Meus anúncios' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(await screen.findByRole('article', { name: 'Caixa de som' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reativar' })).toBeInTheDocument();
  });

  it('começa em Meus anúncios, ativos, com propostas, aluguéis e anúncios', async () => {
    mockApi();
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    expect(await screen.findByRole('heading', { name: 'Aluguéis' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Meus anúncios' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('tab', { name: 'Ativos' })).toHaveAttribute('aria-selected', 'true');

    const rental = await card('Caixa de som, Atrasado');
    expect(rental).toHaveTextContent('10/11/2026 a 12/11/2026 · 3 dias · R$ 45,00');
    expect(rental).toHaveTextContent('Locatário: @davi_teste · (53) 91111-1111');
    // O dono não cancela aluguel aceito (RN-51).
    expect(within(rental).queryByRole('button', { name: /Cancelar/ })).not.toBeInTheDocument();

    const own = await screen.findByRole('article', { name: 'Caixa de som' });
    expect(own).toHaveTextContent('Pausado · Alugado');
    expect(within(own).getByRole('button', { name: 'Reativar' })).toBeInTheDocument();
  });

  it('Itens que estou alugando mostra a situação e o cancelar só quando vale (F-36)', async () => {
    mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    await user.click(await screen.findByRole('tab', { name: 'Itens que estou alugando' }));

    const pending = await card('Barraca para 4 pessoas');
    expect(within(pending).getByText('Aguardando')).toBeInTheDocument();
    expect(within(pending).getByRole('button', { name: 'Cancelar proposta' })).toBeInTheDocument();

    // Aceito com início amanhã: hoje é a véspera, ainda dá para cancelar.
    const reserved = await card('Furadeira de impacto');
    expect(within(reserved).getByRole('button', { name: 'Cancelar aluguel' })).toBeInTheDocument();
    expect(reserved).toHaveTextContent('1 dia');

    // Já começou: sem cancelar; conta excluída aparece como "usuário excluído" (RN-19).
    const ongoing = await card('Bicicleta aro 29');
    expect(within(ongoing).queryByRole('button', { name: /Cancelar/ })).not.toBeInTheDocument();
    expect(ongoing).toHaveTextContent('Dono: usuário excluído');
  });

  it('o histórico vem de scope=history (RN-66)', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    // Valor desconhecido na URL volta para Ativos.
    renderWithProviders(<AppRoutes />, { route: '/alugueis?visao=alugando&aba=xyz' });

    expect(await card('Barraca para 4 pessoas')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Histórico' }));

    const done = await card('Projetor Full HD');
    expect(within(done).getByText('Concluído')).toBeInTheDocument();
    expect(within(done).queryByRole('button', { name: /Cancelar/ })).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([url]) => url === '/api/me/rentals?role=renter&scope=history&limit=20',
      ),
    ).toBe(true);
  });

  it('cancelar pede confirmação e chama a API', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis?visao=alugando' });

    const pending = await card('Barraca para 4 pessoas');
    await user.click(within(pending).getByRole('button', { name: 'Cancelar proposta' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Cancelar proposta?' });
    await user.click(within(dialog).getByRole('button', { name: 'Sim, cancelar' }));

    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url === '/api/rentals/r1/cancel')).toBe(true),
    );
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('409 CANCEL_NOT_ALLOWED vira uma mensagem clara', async () => {
    mockApi({
      cancel: () =>
        jsonResponse(409, { error: { code: 'CANCEL_NOT_ALLOWED', message: 'Não permitido.' } }),
    });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis?visao=alugando' });

    const pending = await card('Barraca para 4 pessoas');
    await user.click(within(pending).getByRole('button', { name: 'Cancelar proposta' }));
    await user.click(screen.getByRole('button', { name: 'Sim, cancelar' }));

    expect(await within(pending).findByRole('alert')).toHaveTextContent(
      'Não é mais possível cancelar: o aluguel já começou.',
    );
  });
});
