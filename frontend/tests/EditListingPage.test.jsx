import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const LISTING = {
  id: 'l1',
  is_owner: true,
  title: 'Furadeira de impacto',
  description: 'Acompanha maleta.',
  category: { id: 1, name: 'Ferramentas' },
  tags: [{ name: 'ferramenta' }],
  daily_price: '25.00',
  max_days: 7,
  available_from: '2099-01-01',
  available_until: '2099-01-31',
  pickup_cep: '96200000',
  pickup_street: 'Rua das Flores',
  pickup_number: '100',
  pickup_complement: null,
  pickup_neighborhood: 'Centro',
  pickup_city: 'Rio Grande',
  pickup_state: 'RS',
  photos: [
    { id: 10, url: '/uploads/a.jpg' },
    { id: 11, url: '/uploads/b.jpg' },
  ],
};

function mockApi({ listing = LISTING, patch = () => jsonResponse(200, { id: 'l1' }) } = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 'u1', username: 'ana_teste' });
    if (url === '/api/categories')
      return jsonResponse(200, [
        { id: 1, name: 'Ferramentas' },
        { id: 2, name: 'Livros' },
      ]);
    if (url === '/api/listings/l1' && options.method === 'GET') {
      return typeof listing === 'function' ? listing() : jsonResponse(200, listing);
    }
    if (url === '/api/listings/l1' && options.method === 'PATCH') return patch();
    throw new Error(`URL inesperada: ${options.method} ${url}`);
  });
}

const patchCalls = (fetchMock) =>
  fetchMock.mock.calls.filter(([, options]) => options?.method === 'PATCH');

async function renderEdit() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/anuncios/l1/editar' });
  await screen.findByRole('heading', { name: 'Editar anúncio', level: 1 });
  await screen.findByRole('option', { name: 'Ferramentas' });
  return user;
}

describe('editar anúncio (F-41)', () => {
  it('abre com os dados e as fotos atuais', async () => {
    mockApi();
    await renderEdit();

    expect(screen.getByLabelText(/Nome do item/)).toHaveValue('Furadeira de impacto');
    expect(screen.getByLabelText(/Categoria/)).toHaveValue('1');
    expect(screen.getByLabelText(/Valor por dia/)).toHaveValue('25,00');
    expect(screen.getByLabelText(/^CEP/)).toHaveValue('96200-000');
    expect(screen.getByText('ferramenta')).toBeInTheDocument();
    expect(screen.getAllByRole('img').map((img) => img.getAttribute('src'))).toEqual([
      '/uploads/a.jpg',
      '/uploads/b.jpg',
    ]);
  });

  it('envia só o que mudou e as fotos como keep_photo_ids[] e photos[]', async () => {
    const fetchMock = mockApi();
    const user = await renderEdit();

    await user.clear(screen.getByLabelText(/Valor por dia/));
    await user.type(screen.getByLabelText(/Valor por dia/), '30');
    await user.click(screen.getByRole('button', { name: 'Usar foto 2 como capa' }));
    await user.upload(
      screen.getByLabelText(/Adicionar fotos/),
      new File(['x'], 'nova.jpg', { type: 'image/jpeg' }),
    );
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }));

    expect(await screen.findByRole('heading', { name: 'Item' })).toBeInTheDocument();
    const [[, options]] = patchCalls(fetchMock);
    const body = options.body;
    expect([...body.keys()].filter((key, index, keys) => keys.indexOf(key) === index)).toEqual([
      'daily_price',
      'keep_photo_ids[]',
      'photos[]',
    ]);
    expect(body.get('daily_price')).toBe('30.00');
    expect(body.getAll('keep_photo_ids[]')).toEqual(['11', '10']);
    expect(body.getAll('photos[]').map((file) => file.name)).toEqual(['nova.jpg']);
  });

  it('foto nova não passa à frente das salvas', async () => {
    mockApi();
    const user = await renderEdit();

    await user.upload(
      screen.getByLabelText(/Adicionar fotos/),
      new File(['x'], 'nova.jpg', { type: 'image/jpeg' }),
    );

    expect(screen.getByRole('button', { name: 'Mover foto 3 para a esquerda' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Usar foto 3 como capa' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mover foto 1 para a direita' })).toBeEnabled();
  });

  it('trocar o local de retirada envia todos os campos pickup_*', async () => {
    const fetchMock = mockApi();
    const user = await renderEdit();

    await user.clear(screen.getByLabelText(/^Número/));
    await user.type(screen.getByLabelText(/^Número/), '200');
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }));

    await screen.findByRole('heading', { name: 'Item' });
    const body = patchCalls(fetchMock)[0][1].body;
    expect(body.get('pickup_number')).toBe('200');
    expect(body.get('pickup_cep')).toBe('96200000');
    expect(body.get('pickup_state')).toBe('RS');
    expect(body.has('title')).toBe(false);
  });

  it('sem alterações volta ao anúncio sem chamar a API', async () => {
    const fetchMock = mockApi();
    const user = await renderEdit();

    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }));

    expect(await screen.findByRole('heading', { name: 'Item' })).toBeInTheDocument();
    expect(patchCalls(fetchMock)).toHaveLength(0);
  });

  it('RN-62: 409 LISTING_HAS_ACTIVE_RENTAL é explicado em linguagem clara', async () => {
    mockApi({
      patch: () =>
        jsonResponse(409, {
          error: { code: 'LISTING_HAS_ACTIVE_RENTAL', message: 'Conflito.' },
        }),
    });
    const user = await renderEdit();

    await user.clear(screen.getByLabelText(/^Máximo de dias/));
    await user.type(screen.getByLabelText(/^Máximo de dias/), '3');
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        'aluguel aceito em andamento ou agendado que ficaria fora da nova janela',
      ),
    );
    expect(screen.getByLabelText(/Disponível até/)).toHaveAccessibleDescription(
      'Um aluguel aceito ficaria fora da janela.',
    );
  });

  it('RN-60: quem não é dono não vê o formulário', async () => {
    mockApi({ listing: { ...LISTING, is_owner: false } });
    renderWithProviders(<AppRoutes />, { route: '/anuncios/l1/editar' });

    expect(
      await screen.findByRole('heading', { name: 'Você não pode editar este anúncio' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver anúncio' })).toHaveAttribute('href', '/itens/l1');
    expect(screen.queryByRole('button', { name: 'Salvar alterações' })).not.toBeInTheDocument();
  });

  it('403 da API ao salvar mostra a mensagem', async () => {
    mockApi({
      patch: () =>
        jsonResponse(403, { error: { code: 'FORBIDDEN', message: 'Só o dono edita o anúncio.' } }),
    });
    const user = await renderEdit();

    await user.type(screen.getByLabelText(/Nome do item/), ' nova');
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Só o dono edita o anúncio.');
  });
});
