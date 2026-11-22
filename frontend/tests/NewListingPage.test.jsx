import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const ME = {
  id: 'u1',
  username: 'ana_teste',
  cep: '96200000',
  street: 'Rua das Flores',
  number: '100',
  complement: '',
  neighborhood: 'Centro',
  city: 'Rio Grande',
  state: 'RS',
};
const CATEGORIES = [
  { id: 1, name: 'Ferramentas' },
  { id: 2, name: 'Eletrônicos' },
];

function mockApi(createResponse = () => jsonResponse(201, { id: 'l99' })) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    if (url === '/api/auth/me') return jsonResponse(200, ME);
    if (url === '/api/categories') return jsonResponse(200, CATEGORIES);
    if (url === '/api/listings' && options.method === 'POST') return createResponse();
    // Página do anúncio criado, aberta depois do 201.
    if (/^\/api\/listings\/[^/]+$/.test(url)) {
      return jsonResponse(200, { id: 'novo', title: 'Anúncio criado', is_owner: true, photos: [] });
    }
    if (url.endsWith('/booked-periods')) return jsonResponse(200, []);
    throw new Error(`URL inesperada: ${options.method} ${url}`);
  });
}

const postCalls = (fetchMock) =>
  fetchMock.mock.calls.filter(
    ([url, options]) => url === '/api/listings' && options?.method === 'POST',
  );

const image = (name, type = 'image/jpeg') => new File(['x'], name, { type });

async function renderNewListing() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/anunciar' });
  await screen.findByRole('heading', { name: 'Anunciar item', level: 1 });
  await screen.findByRole('option', { name: 'Ferramentas' });
  return user;
}

async function fillValid(user) {
  await user.upload(screen.getByLabelText(/Adicionar fotos/), [
    image('frente.jpg'),
    image('lado.png', 'image/png'),
  ]);
  await user.type(screen.getByLabelText(/Nome do item/), 'Furadeira de impacto');
  await user.type(screen.getByLabelText(/Descrição/), 'Acompanha maleta e brocas.');
  await user.selectOptions(screen.getByLabelText(/Categoria/), 'Ferramentas');
  await user.type(screen.getByLabelText(/^Tags/), 'Ferramenta{Enter}obra,');
  await user.type(screen.getByLabelText(/Valor por dia/), '25,5');
  await user.type(screen.getByLabelText(/Máximo de dias/), '7');
  fireEvent.change(screen.getByLabelText(/Disponível a partir de/), {
    target: { value: '2099-01-01' },
  });
  fireEvent.change(screen.getByLabelText(/Disponível até/), { target: { value: '2099-01-31' } });
}

describe('criar anúncio (F-38)', () => {
  it('RN-59: o local de retirada vem do cadastro e as categorias da API', async () => {
    mockApi();
    await renderNewListing();

    expect(screen.getByLabelText(/^CEP/)).toHaveValue('96200-000');
    expect(screen.getByLabelText(/^Rua/)).toHaveValue('Rua das Flores');
    expect(screen.getByLabelText(/^Bairro/)).toHaveValue('Centro');
    expect(screen.getByLabelText(/^UF/)).toHaveValue('RS');
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual(
      expect.arrayContaining(['Ferramentas', 'Eletrônicos']),
    );
  });

  it('RN-53: sem preencher mostra os erros, foca as fotos e não chama a API', async () => {
    const fetchMock = mockApi();
    const user = await renderNewListing();

    await user.click(screen.getByRole('button', { name: 'Publicar anúncio' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Revise os campos destacados.');
    expect(screen.getByText('Adicione ao menos 1 foto.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Adicionar fotos/)).toHaveFocus();
    expect(screen.getByLabelText(/Nome do item/)).toHaveAccessibleDescription('Campo obrigatório.');
    expect(postCalls(fetchMock)).toHaveLength(0);
  });

  it('envia multipart com a capa escolhida, tags e valores sem máscara, e abre o anúncio', async () => {
    const fetchMock = mockApi();
    const user = await renderNewListing();
    await fillValid(user);

    // A segunda foto vira capa.
    await user.click(screen.getByRole('button', { name: 'Usar foto 2 como capa' }));
    expect(screen.getByAltText('Prévia da foto 1 (capa)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Publicar anúncio' }));

    expect(await screen.findByRole('region', { name: 'Seu anúncio' })).toBeInTheDocument();
    const [[, options]] = postCalls(fetchMock);
    const body = options.body;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get('title')).toBe('Furadeira de impacto');
    expect(body.get('category_id')).toBe('1');
    expect(body.get('daily_price')).toBe('25.50');
    expect(body.get('max_days')).toBe('7');
    expect(body.get('available_from')).toBe('2099-01-01');
    expect(body.get('available_until')).toBe('2099-01-31');
    expect(body.getAll('tags[]')).toEqual(['Ferramenta', 'obra']);
    expect(body.get('pickup_cep')).toBe('96200000');
    expect(body.getAll('photos[]').map((file) => file.name)).toEqual(['lado.png', 'frente.jpg']);
    // Multipart: o navegador define o Content-Type com o boundary.
    expect(options.headers['Content-Type']).toBeUndefined();
  });

  it('fotos: recusa tipo inválido, reordena e remove', async () => {
    mockApi();
    const user = userEvent.setup({ applyAccept: false });
    renderWithProviders(<AppRoutes />, { route: '/anunciar' });
    const input = await screen.findByLabelText(/Adicionar fotos/);

    await user.upload(input, [
      image('a.jpg'),
      image('b.gif', 'image/gif'),
      image('c.webp', 'image/webp'),
    ]);

    expect(screen.getByText('b.gif: use JPEG, PNG ou WebP.')).toBeInTheDocument();
    expect(screen.getAllByRole('img').map((img) => img.alt)).toEqual([
      'Prévia da foto 1 (capa)',
      'Prévia da foto 2',
    ]);
    await user.click(screen.getByRole('button', { name: 'Mover foto 1 para a direita' }));
    await user.click(screen.getByRole('button', { name: 'Remover foto 1' }));
    expect(screen.getAllByRole('img')).toHaveLength(1);
  });

  it('fotos: no máximo 5', async () => {
    mockApi();
    const user = await renderNewListing();
    const files = ['1', '2', '3', '4', '5', '6'].map((n) => image(`${n}.jpg`));

    await user.upload(screen.getByLabelText(/Adicionar fotos/), files);

    expect(screen.getAllByRole('img')).toHaveLength(5);
    expect(screen.queryByLabelText(/Adicionar fotos/)).not.toBeInTheDocument();
  });

  it('RN-57: tags repetidas (sem acento/maiúscula) não entram e o limite é 5', async () => {
    mockApi();
    const user = await renderNewListing();
    const input = screen.getByLabelText(/^Tags/);

    await user.type(input, 'Ferramenta{Enter}ferramentá{Enter}');
    expect(input).toHaveAccessibleDescription(expect.stringContaining('já foi adicionada'));
    await user.type(input, 'b{Enter}c{Enter}d{Enter}e{Enter}');

    const list = screen.getByRole('list', { name: 'Tags adicionadas' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(5);
    expect(input).toBeDisabled();
    await user.click(within(list).getByRole('button', { name: 'Remover tag b' }));
    expect(input).toBeEnabled();
  });

  it('RN-55: máximo de dias maior que a janela é recusado na tela', async () => {
    const fetchMock = mockApi();
    const user = await renderNewListing();
    await fillValid(user);
    fireEvent.change(screen.getByLabelText(/Disponível até/), { target: { value: '2099-01-03' } });

    await user.click(screen.getByRole('button', { name: 'Publicar anúncio' }));

    expect(screen.getByLabelText(/Máximo de dias/)).toHaveAccessibleDescription(
      'O máximo de dias não pode passar do tamanho da janela (3 dias).',
    );
    expect(postCalls(fetchMock)).toHaveLength(0);
  });

  it('erros da API aparecem nos campos (422) e nas fotos (413)', async () => {
    let response = () =>
      jsonResponse(422, {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Dados inválidos.',
          fields: { title: 'Nome já usado em outro anúncio seu.' },
        },
      });
    mockApi(() => response());
    const user = await renderNewListing();
    await fillValid(user);

    await user.click(screen.getByRole('button', { name: 'Publicar anúncio' }));
    await waitFor(() =>
      expect(screen.getByLabelText(/Nome do item/)).toHaveAccessibleDescription(
        'Nome já usado em outro anúncio seu.',
      ),
    );
    expect(screen.getByLabelText(/Nome do item/)).toHaveFocus();

    response = () =>
      jsonResponse(413, { error: { code: 'FILE_TOO_LARGE', message: 'Foto acima de 5 MB.' } });
    await user.click(screen.getByRole('button', { name: 'Publicar anúncio' }));
    // A mensagem aparece no resumo e no bloco de fotos, que recebe o foco.
    await waitFor(() => expect(screen.getAllByText('Foto acima de 5 MB.')).toHaveLength(2));
    expect(screen.getByLabelText(/Adicionar fotos/)).toHaveFocus();
  });
});
