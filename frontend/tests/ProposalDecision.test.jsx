import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const PENDING = {
  id: 'p1',
  status: 'pending',
  situation: 'Aguardando',
  start_date: '2026-12-10',
  end_date: '2026-12-12',
  estimated_total: '45.00',
  listing: { id: 11, title: 'Caixa de som', cover_photo: null },
  renter: { username: 'davi_teste' },
};
const ACCEPTED = {
  ...PENDING,
  status: 'accepted',
  situation: 'Reservado',
  renter: { username: 'davi_teste', phone: '(53) 91111-1111' },
};

/** API fictícia: a proposta vira aceita ou recusada conforme a ação. */
function mockApi(responses = {}) {
  let row = PENDING;
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url.startsWith('/api/me/rentals?role=owner&scope=active')) {
      return jsonResponse(200, { items: row ? [row] : [], next_cursor: null });
    }
    if (url.startsWith('/api/me/')) return jsonResponse(200, { items: [], next_cursor: null });
    if (url === '/api/rentals/p1/accept' && method === 'POST') {
      if (responses.accept) return responses.accept();
      row = ACCEPTED;
      return jsonResponse(200, { id: 'p1', status: 'accepted' });
    }
    if (url === '/api/rentals/p1/reject' && method === 'POST') {
      row = null;
      return jsonResponse(200, { id: 'p1', status: 'rejected' });
    }
    throw new Error(`URL inesperada: ${method} ${url}`);
  });
  return { fetchMock, setRow: (next) => (row = next) };
}

async function renderOwnerView() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/alugueis' });
  const card = await screen.findByRole('article', { name: /^Caixa de som, Aguardando/ });
  return { user, card };
}

describe('aceitar e recusar proposta (F-39, F-44)', () => {
  it('aceitar confirma, chama a API e mostra o telefone do locatário', async () => {
    const { fetchMock } = mockApi();
    const { user, card } = await renderOwnerView();

    expect(card).not.toHaveTextContent('(53)');
    await user.click(within(card).getByRole('button', { name: 'Aceitar' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Aceitar proposta?' });
    expect(dialog).toHaveTextContent('se sobrepõem são recusadas automaticamente');
    await user.click(within(dialog).getByRole('button', { name: 'Aceitar proposta' }));

    const accepted = await screen.findByRole('article', { name: /^Caixa de som, Reservado/ });
    expect(accepted).toHaveTextContent('@davi_teste · (53) 91111-1111');
    expect(within(accepted).queryByRole('button', { name: 'Aceitar' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/rentals/p1/accept')).toHaveLength(
      1,
    );
  });

  it('recusar confirma e tira a proposta dos ativos', async () => {
    const { fetchMock } = mockApi();
    const { user, card } = await renderOwnerView();

    await user.click(within(card).getByRole('button', { name: 'Recusar' }));
    await user.click(screen.getByRole('button', { name: 'Recusar proposta' }));

    expect(
      await screen.findByText('Nenhuma proposta ou aluguel em andamento nos seus anúncios.'),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/rentals/p1/reject')).toBe(true);
  });

  it('Voltar fecha a confirmação sem chamar a API', async () => {
    const { fetchMock } = mockApi();
    const { user, card } = await renderOwnerView();

    await user.click(within(card).getByRole('button', { name: 'Aceitar' }));
    await user.click(screen.getByRole('button', { name: 'Voltar' }));

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url.startsWith('/api/rentals/'))).toBe(false);
  });

  it.each([
    ['RENTAL_OVERLAP', 'Outro aluguel já foi aceito para essas datas'],
    ['PROPOSAL_EXPIRED', 'Esta proposta expirou'],
    ['INVALID_STATE', 'Esta proposta já foi respondida ou cancelada.'],
  ])('409 %s vira uma mensagem clara', async (code, text) => {
    mockApi({ accept: () => jsonResponse(409, { error: { code, message: 'Conflito.' } }) });
    const { user, card } = await renderOwnerView();

    await user.click(within(card).getByRole('button', { name: 'Aceitar' }));
    await user.click(screen.getByRole('button', { name: 'Aceitar proposta' }));

    expect(await within(card).findByRole('alert')).toHaveTextContent(text);
  });

  it('o locatário vê o endereço completo depois do aceite (RN-35)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (url === '/api/auth/me') return jsonResponse(200, { id: 2, username: 'davi_teste' });
      if (url.startsWith('/api/me/rentals?role=renter&scope=active')) {
        return jsonResponse(200, {
          items: [
            {
              ...ACCEPTED,
              start_date: '2099-12-10',
              end_date: '2099-12-12',
              listing: {
                ...ACCEPTED.listing,
                pickup_street: 'Rua Exemplo',
                pickup_number: '100',
                pickup_complement: 'Casa 2',
                pickup_neighborhood: 'Centro',
                pickup_city: 'Rio Grande',
              },
              owner: { username: 'ana_teste', phone: '(53) 90000-0000' },
            },
          ],
          next_cursor: null,
        });
      }
      throw new Error(`URL inesperada: ${url}`);
    });
    renderWithProviders(<AppRoutes />, { route: '/alugueis?visao=alugando' });

    const card = await screen.findByRole('article', { name: /^Caixa de som/ });
    expect(card).toHaveTextContent('Retirada: Rua Exemplo, 100, Casa 2 · Centro, Rio Grande');
    expect(card).toHaveTextContent('Dono: @ana_teste · (53) 90000-0000');
    expect(within(card).queryByRole('button', { name: 'Aceitar' })).not.toBeInTheDocument();
  });
});
