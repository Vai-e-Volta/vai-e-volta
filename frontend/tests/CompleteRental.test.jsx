import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios. O relógio fica em 20/11/2026.
const base = {
  status: 'accepted',
  estimated_total: '45.00',
  renter: { username: 'davi_teste', phone: '(53) 91111-1111' },
};
const ROWS = [
  {
    ...base,
    id: 'a1',
    situation: 'Em andamento',
    start_date: '2026-11-20',
    end_date: '2026-11-22',
    listing: { id: 11, title: 'Caixa de som', cover_photo: null },
  },
  {
    ...base,
    id: 'a2',
    situation: 'Atrasado',
    start_date: '2026-11-10',
    end_date: '2026-11-12',
    listing: { id: 12, title: 'Kit churrasco', cover_photo: null },
  },
  {
    ...base,
    id: 'a3',
    situation: 'Reservado',
    start_date: '2026-11-21',
    end_date: '2026-11-23',
    listing: { id: 13, title: 'Barraca para 4 pessoas', cover_photo: null },
  },
];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-20T12:00:00-03:00'));
});

afterEach(() => {
  vi.useRealTimers();
});

function mockApi(complete) {
  let rows = ROWS;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url.startsWith('/api/me/rentals?role=owner&scope=active')) {
      return jsonResponse(200, { items: rows, next_cursor: null });
    }
    if (url.startsWith('/api/me/')) return jsonResponse(200, { items: [], next_cursor: null });
    if (url === '/api/rentals/a1/complete' && method === 'POST') {
      if (complete) return complete();
      rows = rows.filter((row) => row.id !== 'a1');
      return jsonResponse(200, { id: 'a1', status: 'completed' });
    }
    throw new Error(`URL inesperada: ${method} ${url}`);
  });
}

const card = (name) => screen.findByRole('article', { name: new RegExp(`^${name}`) });

describe('marcar como devolvido (F-40, RN-64)', () => {
  it('aparece só no aluguel aceito que já começou', async () => {
    mockApi();
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    for (const name of ['Caixa de som', 'Kit churrasco']) {
      expect(
        within(await card(name)).getByRole('button', { name: 'Marcar como devolvido' }),
      ).toBeInTheDocument();
    }
    expect(
      within(await card('Barraca para 4 pessoas')).queryByRole('button', {
        name: 'Marcar como devolvido',
      }),
    ).not.toBeInTheDocument();
  });

  it('confirma, chama a API e tira o aluguel dos ativos', async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    await user.click(
      within(await card('Caixa de som')).getByRole('button', { name: 'Marcar como devolvido' }),
    );
    const dialog = screen.getByRole('alertdialog', { name: 'Marcar como devolvido?' });
    expect(dialog).toHaveTextContent('Confirme só depois de receber o item.');
    await user.click(within(dialog).getByRole('button', { name: 'Confirmar devolução' }));

    await vi.waitFor(() =>
      expect(screen.queryByRole('article', { name: /^Caixa de som/ })).not.toBeInTheDocument(),
    );
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/rentals/a1/complete')).toBe(true);
  });

  it('erro da API vira uma mensagem clara', async () => {
    mockApi(() =>
      jsonResponse(409, { error: { code: 'INVALID_STATE', message: 'Estado inválido.' } }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/alugueis' });

    const row = await card('Caixa de som');
    await user.click(within(row).getByRole('button', { name: 'Marcar como devolvido' }));
    await user.click(screen.getByRole('button', { name: 'Confirmar devolução' }));

    expect(await within(row).findByRole('alert')).toHaveTextContent(
      'Só dá para marcar como devolvido um aluguel aceito que já começou.',
    );
  });
});
