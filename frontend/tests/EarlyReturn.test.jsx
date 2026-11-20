import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios. O relógio fica em 20/11/2026.
const ONGOING = {
  id: 'e1',
  status: 'accepted',
  situation: 'Em andamento',
  start_date: '2026-11-18',
  end_date: '2026-11-24',
  estimated_total: '105.00',
  daily_price_snapshot: '15.00',
  listing: { id: 11, title: 'Caixa de som', cover_photo: null },
  owner: { username: 'ana_teste', phone: '(53) 90000-0000' },
  renter: { username: 'davi_teste', phone: '(53) 91111-1111' },
};
const LAST_DAY = {
  ...ONGOING,
  id: 'e2',
  start_date: '2026-11-19',
  end_date: '2026-11-20',
  estimated_total: '30.00',
  listing: { id: 12, title: 'Kit churrasco', cover_photo: null },
};
const REQUESTED = { ...ONGOING, return_requested_at: '2026-11-20T10:00:00-03:00' };

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-20T12:00:00-03:00'));
});

afterEach(() => {
  vi.useRealTimers();
});

function mockApi({ renter = [ONGOING, LAST_DAY], owner = [], history = [] } = {}) {
  let renterRows = renter;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    if (url === '/api/auth/me') return jsonResponse(200, { id: 2, username: 'davi_teste' });
    if (url.startsWith('/api/me/rentals?role=renter&scope=active')) {
      return jsonResponse(200, { items: renterRows, next_cursor: null });
    }
    if (url.startsWith('/api/me/rentals?role=renter&scope=history')) {
      return jsonResponse(200, { items: history, next_cursor: null });
    }
    if (url.startsWith('/api/me/rentals?role=owner&scope=active')) {
      return jsonResponse(200, { items: owner, next_cursor: null });
    }
    if (url.startsWith('/api/me/')) return jsonResponse(200, { items: [], next_cursor: null });
    if (url === '/api/rentals/e1/return-request' && method === 'POST') {
      renterRows = [REQUESTED, LAST_DAY];
      return jsonResponse(200, { id: 'e1', status: 'accepted' });
    }
    throw new Error(`URL inesperada: ${method} ${url}`);
  });
}

const card = (name) => screen.findByRole('article', { name: new RegExp(`^${name}`) });

describe('devolver antes do prazo (F-37, RN-50)', () => {
  it('aparece para o locatário só em aluguel em andamento antes do último dia', async () => {
    mockApi();
    renderWithProviders(<AppRoutes />, { route: '/alugueis?visao=alugando' });

    expect(
      within(await card('Caixa de som')).getByRole('button', { name: 'Devolver antes do prazo' }),
    ).toBeInTheDocument();
    expect(
      within(await card('Kit churrasco')).queryByRole('button', {
        name: 'Devolver antes do prazo',
      }),
    ).not.toBeInTheDocument();
  });

  it('mostra o valor recalculado, avisa o dono e some depois do aviso', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis?visao=alugando' });

    const row = await card('Caixa de som');
    await user.click(within(row).getByRole('button', { name: 'Devolver antes do prazo' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Devolver antes do prazo?' });
    expect(dialog).toHaveTextContent('passa de 7 dias · R$ 105,00 para 3 dias · R$ 45,00');
    await user.click(within(dialog).getByRole('button', { name: 'Avisar o dono' }));

    expect(
      await within(row).findByText(
        'Você avisou a devolução em 20/11/2026. Falta o dono confirmar.',
      ),
    ).toBeInTheDocument();
    expect(
      within(row).queryByRole('button', { name: 'Devolver antes do prazo' }),
    ).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/rentals/e1/return-request')).toBe(
      true,
    );
  });

  it('o dono vê o aviso e confirma vendo o valor recalculado', async () => {
    mockApi({ owner: [REQUESTED] });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    const row = await card('Caixa de som');
    expect(row).toHaveTextContent('O locatário avisou a devolução em 20/11/2026.');
    await user.click(within(row).getByRole('button', { name: 'Marcar como devolvido' }));

    expect(screen.getByRole('alertdialog', { name: 'Marcar como devolvido?' })).toHaveTextContent(
      'passa de 7 dias · R$ 105,00 para 3 dias · R$ 45,00',
    );
  });

  it('o histórico mostra a devolução antecipada', async () => {
    mockApi({
      history: [
        {
          ...ONGOING,
          status: 'completed',
          situation: 'Concluído',
          end_date: '2026-11-20',
          estimated_total: '45.00',
          returned_on: '2026-11-20',
          original_end_date: '2026-11-24',
        },
      ],
    });
    renderWithProviders(<AppRoutes />, { route: '/alugueis?visao=alugando&aba=historico' });

    const row = await card('Caixa de som');
    expect(row).toHaveTextContent('18/11/2026 a 20/11/2026 · 3 dias · R$ 45,00');
    expect(row).toHaveTextContent('Devolvido em 20/11/2026, antes do fim previsto (24/11/2026).');
  });
});
