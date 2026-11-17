import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const ME = {
  id: 'u1',
  full_name: 'Ana Teste da Silva',
  username: 'ana_teste',
  email: 'ana@exemplo.com',
  cpf: '52998224725',
  phone: '53999998888',
  cep: '96200000',
  street: 'Rua das Flores',
  number: '100',
  complement: 'Apto 2',
  neighborhood: 'Centro',
  city: 'Rio Grande',
  state: 'RS',
};

/** Simula a API; `handlers` responde a PATCH /api/me e PUT /api/me/password. */
function mockApi(handlers = {}) {
  let me = ME;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    if (url === '/api/auth/me') return jsonResponse(200, me);
    if (url === '/api/me' && options.method === 'PATCH') {
      const response = handlers.patch(JSON.parse(options.body));
      if (response.ok) me = { ...me, ...JSON.parse(options.body) };
      return response;
    }
    if (url === '/api/me/password' && options.method === 'PUT') {
      return handlers.password(JSON.parse(options.body));
    }
    throw new Error(`URL inesperada: ${options.method} ${url}`);
  });
}

const callsTo = (fetchMock, url, method) =>
  fetchMock.mock.calls.filter(
    ([calledUrl, options]) => calledUrl === url && options?.method === method,
  );

async function renderSettings() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/configuracoes' });
  await screen.findByRole('heading', { name: 'Configurações', level: 1 });
  return user;
}

describe('configurações: editar dados (F-11)', () => {
  it('abre com os dados atuais, com máscaras', async () => {
    mockApi();
    await renderSettings();

    expect(screen.getByLabelText(/Nome completo/)).toHaveValue('Ana Teste da Silva');
    expect(screen.getByLabelText(/^CPF/)).toHaveValue('529.982.247-25');
    expect(screen.getByLabelText(/Telefone celular/)).toHaveValue('(53) 99999-8888');
    expect(screen.getByLabelText(/^CEP/)).toHaveValue('96200-000');
    expect(screen.getByLabelText(/^UF/)).toHaveValue('RS');
  });

  it('envia só os campos alterados, sem máscara, e confirma', async () => {
    const fetchMock = mockApi({ patch: () => jsonResponse(200, {}) });
    const user = await renderSettings();

    await user.clear(screen.getByLabelText(/Telefone celular/));
    await user.type(screen.getByLabelText(/Telefone celular/), '53988887777');
    await user.clear(screen.getByLabelText(/Complemento/));
    await user.click(screen.getByRole('button', { name: 'Salvar dados' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Dados atualizados.');
    const [[, options]] = callsTo(fetchMock, '/api/me', 'PATCH');
    expect(JSON.parse(options.body)).toEqual({ phone: '53988887777', complement: null });
    // A sessão é recarregada de /api/auth/me depois de salvar.
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/auth/me')).toHaveLength(2);
  });

  it('sem alterações não chama a API', async () => {
    const fetchMock = mockApi();
    const user = await renderSettings();

    await user.click(screen.getByRole('button', { name: 'Salvar dados' }));

    expect(screen.getByRole('status')).toHaveTextContent('Nenhuma alteração para salvar.');
    expect(callsTo(fetchMock, '/api/me', 'PATCH')).toHaveLength(0);
  });

  it('valida na tela com as regras do cadastro e foca o campo com erro', async () => {
    const fetchMock = mockApi();
    const user = await renderSettings();

    await user.clear(screen.getByLabelText(/^CPF/));
    await user.type(screen.getByLabelText(/^CPF/), '11111111111');
    await user.click(screen.getByRole('button', { name: 'Salvar dados' }));

    expect(screen.getByLabelText(/^CPF/)).toHaveAccessibleDescription('CPF inválido.');
    expect(screen.getByLabelText(/^CPF/)).toHaveFocus();
    expect(callsTo(fetchMock, '/api/me', 'PATCH')).toHaveLength(0);
  });

  it('RN-09: 409 FIELD_IN_USE indica no campo qual dado já está em uso', async () => {
    mockApi({
      patch: () =>
        jsonResponse(409, {
          error: {
            code: 'FIELD_IN_USE',
            message: 'Um dos campos já está em uso.',
            fields: { email: 'Já cadastrado.' },
          },
        }),
    });
    const user = await renderSettings();

    await user.clear(screen.getByLabelText(/^E-mail/));
    await user.type(screen.getByLabelText(/^E-mail/), 'outra@exemplo.com');
    await user.click(screen.getByRole('button', { name: 'Salvar dados' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Um dos campos já está em uso.');
    expect(screen.getByLabelText(/^E-mail/)).toHaveAccessibleDescription(
      'Este e-mail já está cadastrado.',
    );
    expect(screen.getByLabelText(/^E-mail/)).toHaveFocus();
  });
});

describe('configurações: trocar senha (F-12)', () => {
  it('envia current_password e new_password e limpa os campos ao concluir', async () => {
    const fetchMock = mockApi({ password: () => new Response(null, { status: 204 }) });
    const user = await renderSettings();

    await user.type(screen.getByLabelText(/Senha atual/), 'Senha@123');
    await user.type(screen.getByLabelText(/Nova senha/), 'Nova@4567');
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Senha alterada.');
    const [[, options]] = callsTo(fetchMock, '/api/me/password', 'PUT');
    expect(JSON.parse(options.body)).toEqual({
      current_password: 'Senha@123',
      new_password: 'Nova@4567',
    });
    expect(screen.getByLabelText(/Senha atual/)).toHaveValue('');
    expect(screen.getByLabelText(/Nova senha/)).toHaveValue('');
  });

  it('RN-16: senha atual errada (401) mostra mensagem clara e não encerra a sessão', async () => {
    mockApi({
      password: () =>
        jsonResponse(401, {
          error: { code: 'INVALID_CREDENTIALS', message: 'Credenciais inválidas.' },
        }),
    });
    const user = await renderSettings();

    await user.type(screen.getByLabelText(/Senha atual/), 'Errada@123');
    await user.type(screen.getByLabelText(/Nova senha/), 'Nova@4567');
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('A senha atual está incorreta.');
    expect(screen.getByLabelText(/Senha atual/)).toHaveAccessibleDescription(
      'Senha atual incorreta.',
    );
    expect(screen.getByLabelText(/Senha atual/)).toHaveValue('');
    expect(screen.getByLabelText(/Senha atual/)).toHaveFocus();
    expect(screen.getByRole('heading', { name: 'Configurações', level: 1 })).toBeInTheDocument();
  });

  it('RN-04: nova senha fraca é barrada na tela; 422 da API aparece no campo', async () => {
    const fetchMock = mockApi({
      password: () =>
        jsonResponse(422, {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Dados inválidos.',
            fields: { new_password: 'A nova senha não pode ser igual à atual.' },
          },
        }),
    });
    const user = await renderSettings();

    await user.type(screen.getByLabelText(/Senha atual/), 'Senha@123');
    await user.type(screen.getByLabelText(/Nova senha/), 'fraca');
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }));
    expect(screen.getByLabelText(/Nova senha/)).toHaveAccessibleDescription(
      expect.stringContaining('Use de 8 a 128 caracteres'),
    );
    expect(callsTo(fetchMock, '/api/me/password', 'PUT')).toHaveLength(0);

    await user.clear(screen.getByLabelText(/Nova senha/));
    await user.type(screen.getByLabelText(/Nova senha/), 'Senha@123');
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }));

    expect(await screen.findByText('A nova senha não pode ser igual à atual.')).toBeInTheDocument();
  });
});
