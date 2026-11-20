import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const OWN_LISTING = {
  id: 7,
  title: 'Furadeira de impacto',
  description: 'Com maleta.',
  daily_price: '15.00',
  max_days: 3,
  available_from: '2026-11-01',
  available_until: '2027-01-31',
  category: { id: 1, name: 'Ferramentas' },
  tags: [],
  photos: [],
  pickup_street: 'Rua Exemplo',
  pickup_neighborhood: 'Centro',
  pickup_city: 'Rio Grande',
  pickup_state: 'RS',
  owner: { username: 'ana_teste' },
  status: 'active',
  situation: 'available',
  is_owner: true,
  unavailable: false,
};

const ACTIVE_RENTAL = {
  error: {
    code: 'LISTING_HAS_ACTIVE_RENTAL',
    message: 'O anúncio tem aluguel aceito em curso ou futuro.',
  },
};

/** API fictícia: guarda o status do anúncio e permite forçar a resposta de cada ação. */
function mockApi(responses = {}) {
  let status = 'active';
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/listings/7/booked-periods') return jsonResponse(200, []);
    if (url === '/api/listings/7' && method === 'GET') {
      return jsonResponse(200, { ...OWN_LISTING, status, unavailable: status !== 'active' });
    }
    if (url === '/api/listings/7/pause' && method === 'POST') {
      if (responses.pause) return responses.pause();
      status = 'paused';
      return jsonResponse(200, { id: 7, status });
    }
    if (url === '/api/listings/7/resume' && method === 'POST') {
      if (responses.resume) return responses.resume();
      status = 'active';
      return jsonResponse(200, { id: 7, status });
    }
    if (url === '/api/listings/7' && method === 'DELETE') {
      if (responses.delete) return responses.delete();
      return new Response(null, { status: 204 });
    }
    if (url.startsWith('/api/listings?')) {
      return jsonResponse(200, { items: [], next_cursor: null, total: 0 });
    }
    if (url === '/api/categories' || url.startsWith('/api/tags')) return jsonResponse(200, []);
    if (url === '/api/listings/price-ranges') return jsonResponse(200, { ranges: [] });
    throw new Error(`URL inesperada: ${method} ${url}`);
  });
  return { fetchMock, setStatus: (next) => (status = next) };
}

const calls = (fetchMock, method, url) =>
  fetchMock.mock.calls.filter(([u, options]) => u === url && options?.method === method);

async function renderOwnItem() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/itens/7' });
  const panel = await screen.findByRole('region', { name: 'Seu anúncio' });
  return { user, panel };
}

describe('controles do anunciante (F-41, RN-62)', () => {
  it('pausar pede confirmação, chama a API e mostra o anúncio pausado', async () => {
    const { fetchMock } = mockApi();
    const { user, panel } = await renderOwnItem();

    expect(within(panel).getByText('Ativo · Disponível')).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: 'Pausar' }));

    const dialog = screen.getByRole('alertdialog', { name: 'Pausar anúncio?' });
    expect(dialog).toHaveTextContent('as propostas pendentes são recusadas');
    await user.click(within(dialog).getByRole('button', { name: 'Pausar anúncio' }));

    expect(await within(panel).findByText('Pausado · Disponível')).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: 'Reativar' })).toBeInTheDocument();
    expect(calls(fetchMock, 'POST', '/api/listings/7/pause')).toHaveLength(1);
  });

  it('cancelar a confirmação não chama a API', async () => {
    const { fetchMock } = mockApi();
    const { user, panel } = await renderOwnItem();

    await user.click(within(panel).getByRole('button', { name: 'Excluir' }));
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(calls(fetchMock, 'DELETE', '/api/listings/7')).toHaveLength(0);
  });

  it('reativar não pede confirmação', async () => {
    const { fetchMock, setStatus } = mockApi();
    setStatus('paused');
    const { user, panel } = await renderOwnItem();

    await user.click(within(panel).getByRole('button', { name: 'Reativar' }));

    expect(await within(panel).findByText('Ativo · Disponível')).toBeInTheDocument();
    expect(calls(fetchMock, 'POST', '/api/listings/7/resume')).toHaveLength(1);
  });

  it('409 LISTING_HAS_ACTIVE_RENTAL explica e leva aos aluguéis', async () => {
    mockApi({ pause: () => jsonResponse(409, ACTIVE_RENTAL) });
    const { user, panel } = await renderOwnItem();

    await user.click(within(panel).getByRole('button', { name: 'Pausar' }));
    await user.click(screen.getByRole('button', { name: 'Pausar anúncio' }));

    const alert = await within(panel).findByRole('alert');
    expect(alert).toHaveTextContent('aluguel aceito em andamento ou agendado');
    expect(within(alert).getByRole('link', { name: 'Ver meus aluguéis' })).toHaveAttribute(
      'href',
      '/alugueis',
    );
    expect(within(panel).getByText('Ativo · Disponível')).toBeInTheDocument();
  });

  it('reativar com a janela encerrada mostra a mensagem da API e o caminho para editar', async () => {
    const { setStatus } = mockApi({
      resume: () =>
        jsonResponse(409, {
          error: { code: 'LISTING_WINDOW_ENDED', message: 'A janela do anúncio já terminou.' },
        }),
    });
    setStatus('paused');
    const { user, panel } = await renderOwnItem();

    await user.click(within(panel).getByRole('button', { name: 'Reativar' }));

    const alert = await within(panel).findByRole('alert');
    expect(alert).toHaveTextContent('A janela do anúncio já terminou.');
    expect(within(alert).getByRole('link', { name: 'Editar as datas' })).toHaveAttribute(
      'href',
      '/anuncios/7/editar',
    );
  });

  it('excluir confirma em vermelho, chama DELETE e volta ao feed com aviso', async () => {
    const { fetchMock } = mockApi();
    const { user, panel } = await renderOwnItem();

    await user.click(within(panel).getByRole('button', { name: 'Excluir' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Excluir anúncio?' });
    expect(dialog).toHaveTextContent('Não é possível desfazer.');
    await user.click(within(dialog).getByRole('button', { name: 'Excluir anúncio' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Anúncio excluído.');
    expect(screen.getByRole('heading', { name: 'Itens para alugar' })).toBeInTheDocument();
    expect(calls(fetchMock, 'DELETE', '/api/listings/7')).toHaveLength(1);
  });
});
