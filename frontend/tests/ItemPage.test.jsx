import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const LISTING = {
  id: 7,
  title: 'Barraca para 4 pessoas',
  description: 'Barraca com sobreteto.\nAcompanha estacas.',
  daily_price: '35.00',
  max_days: 5,
  available_from: '2026-12-01',
  available_until: '2027-01-31',
  category: { id: 2, name: 'Camping' },
  tags: [{ name: 'camping' }, 'praia'],
  photos: [
    { id: 11, filename: 'barraca-1.jpg' },
    { id: 12, url: '/uploads/barraca-2.jpg' },
  ],
  pickup_street: 'Rua Exemplo',
  pickup_neighborhood: 'Cassino',
  pickup_city: 'Rio Grande',
  pickup_state: 'RS',
  owner: { username: 'bruno_teste' },
  status: 'active',
  situation: 'available',
  is_owner: false,
  unavailable: false,
};

function mockApi(listingResponse, periods = []) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 1, username: 'ana_teste' });
    if (url === '/api/listings/7') return listingResponse();
    if (url === '/api/listings/7/booked-periods') return jsonResponse(200, { periods });
    throw new Error(`URL inesperada: ${url}`);
  });
}

describe('página do item (F-28, F-29)', () => {
  it('mostra fotos, dados, tags, retirada sem número e anunciante', async () => {
    mockApi(() => jsonResponse(200, LISTING));
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/itens/7' });

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Barraca para 4 pessoas' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Camping')).toBeInTheDocument();
    expect(screen.getByText('R$ 35,00')).toBeInTheDocument();
    expect(screen.getByText(/Acompanha estacas/)).toBeInTheDocument();
    expect(screen.getByText('5 dias por aluguel')).toBeInTheDocument();
    expect(screen.getByText('01/12/2026 a 31/01/2027')).toBeInTheDocument();
    expect(
      within(screen.getByRole('list', { name: 'Tags' })).getAllByRole('listitem'),
    ).toHaveLength(2);
    expect(screen.getByText('Rua Exemplo')).toBeInTheDocument();
    expect(screen.getByText('Cassino, Rio Grande/RS')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '@bruno_teste' })).toHaveAttribute(
      'href',
      '/usuarios/bruno_teste',
    );

    const photo = screen.getByRole('img', { name: 'Barraca para 4 pessoas, foto 1 de 2' });
    expect(photo).toHaveAttribute('src', '/uploads/barraca-1.jpg');
    await user.click(screen.getByRole('button', { name: 'Ver foto 2' }));
    expect(
      screen.getByRole('img', { name: 'Barraca para 4 pessoas, foto 2 de 2' }),
    ).toHaveAttribute('src', '/uploads/barraca-2.jpg');
  });

  it('lista os períodos já reservados', async () => {
    mockApi(
      () => jsonResponse(200, LISTING),
      [
        { start_date: '2026-12-05', end_date: '2026-12-07' },
        { start_date: '2026-12-20', end_date: '2026-12-22' },
      ],
    );
    renderWithProviders(<AppRoutes />, { route: '/itens/7' });

    expect(await screen.findByText('05/12/2026 a 07/12/2026')).toBeInTheDocument();
    expect(screen.getByText('20/12/2026 a 22/12/2026')).toBeInTheDocument();
  });

  it('sem períodos reservados, avisa', async () => {
    mockApi(() => jsonResponse(200, LISTING));
    renderWithProviders(<AppRoutes />, { route: '/itens/7' });

    expect(await screen.findByText('Nenhum período reservado até agora.')).toBeInTheDocument();
  });
});

describe('UT-ITM-01 botão de proposta e visão do dono (RN-33, F-31)', () => {
  it('quem não é dono vê o botão "Propor aluguel"', async () => {
    mockApi(() => jsonResponse(200, LISTING));
    renderWithProviders(<AppRoutes />, { route: '/itens/7' });

    expect(await screen.findByRole('button', { name: 'Propor aluguel' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Editar anúncio' })).not.toBeInTheDocument();
  });

  it('o dono não vê o botão de proposta; vê a situação, editar e o endereço completo', async () => {
    mockApi(() =>
      jsonResponse(200, {
        ...LISTING,
        is_owner: true,
        status: 'paused',
        unavailable: true,
        pickup_number: '100',
        pickup_complement: 'Casa 2',
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/itens/7' });

    const panel = await screen.findByRole('region', { name: 'Seu anúncio' });
    expect(screen.queryByRole('button', { name: 'Propor aluguel' })).not.toBeInTheDocument();
    expect(within(panel).getByText('Pausado · Disponível')).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: 'Editar anúncio' })).toHaveAttribute(
      'href',
      '/anuncios/7/editar',
    );
    expect(screen.getByText('Rua Exemplo, 100 – Casa 2')).toBeInTheDocument();
  });
});

describe('anúncio indisponível e erros (RN-34)', () => {
  it('anúncio pausado ou excluído aparece como indisponível para quem não é dono', async () => {
    mockApi(() => jsonResponse(200, { ...LISTING, unavailable: true }));
    renderWithProviders(<AppRoutes />, { route: '/itens/7' });

    expect(
      await screen.findByRole('heading', { name: 'Anúncio indisponível' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Propor aluguel' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Voltar ao feed' })).toHaveAttribute('href', '/');
  });

  it('404 mostra "Anúncio não encontrado"', async () => {
    mockApi(() =>
      jsonResponse(404, {
        error: { code: 'LISTING_NOT_FOUND', message: 'Anúncio não encontrado.' },
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/itens/7' });

    expect(
      await screen.findByRole('heading', { name: 'Anúncio não encontrado' }),
    ).toBeInTheDocument();
  });
});
