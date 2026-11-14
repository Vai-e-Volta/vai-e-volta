import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

const unauthenticated = () =>
  jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Faça login.' } });

/** Simula a API: sem sessão e com a resposta informada para o cadastro. */
function mockApi(registerResponse) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return unauthenticated();
    if (url === '/api/auth/register') return registerResponse();
    throw new Error(`URL inesperada: ${url}`);
  });
}

function registerCalls(fetchMock) {
  return fetchMock.mock.calls.filter(([url]) => url === '/api/auth/register');
}

async function renderRegisterPage() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/cadastro' });
  await screen.findByRole('heading', { name: 'Criar conta' });
  return user;
}

// Dados fictícios.
async function fillValidForm(user) {
  await user.type(screen.getByLabelText(/Nome completo/), 'Ana Teste');
  await user.type(screen.getByLabelText(/^CPF/), '52998224725');
  await user.type(screen.getByLabelText(/Telefone celular/), '53999990000');
  await user.type(screen.getByLabelText(/Nome de usuário/), 'ana_teste');
  await user.type(screen.getByLabelText(/E-mail/), 'ana@example.com');
  await user.type(screen.getByLabelText(/^Senha/), 'Senha@123');
  await user.type(screen.getByLabelText(/^CEP/), '96200000');
  await user.type(screen.getByLabelText(/^Rua/), 'Rua Exemplo');
  await user.type(screen.getByLabelText(/^Número/), '100');
  await user.type(screen.getByLabelText(/^Bairro/), 'Centro');
  await user.type(screen.getByLabelText(/^Cidade/), 'Rio Grande');
  await user.selectOptions(screen.getByLabelText(/^UF/), 'RS');
}

describe('tela de cadastro (H-001)', () => {
  it('F-01: mostra todos os campos do contrato, com complemento opcional', async () => {
    mockApi(() => jsonResponse(201, {}));
    await renderRegisterPage();

    for (const label of [
      /Nome completo/,
      /^CPF/,
      /Telefone celular/,
      /Nome de usuário/,
      /E-mail/,
      /^Senha/,
      /^CEP/,
      /^Rua/,
      /^Número/,
      /^Bairro/,
      /^Cidade/,
      /^UF/,
    ]) {
      expect(screen.getByLabelText(label)).toBeRequired();
    }
    expect(screen.getByLabelText(/Complemento/)).not.toBeRequired();
    expect(screen.getByLabelText(/^Senha/)).toHaveAttribute('type', 'password');
  });

  it('aplica máscara de CPF, telefone e CEP', async () => {
    mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await user.type(screen.getByLabelText(/^CPF/), '52998224725');
    await user.type(screen.getByLabelText(/Telefone celular/), '53999990000');
    await user.type(screen.getByLabelText(/^CEP/), '96200000');

    expect(screen.getByLabelText(/^CPF/)).toHaveValue('529.982.247-25');
    expect(screen.getByLabelText(/Telefone celular/)).toHaveValue('(53) 99999-0000');
    expect(screen.getByLabelText(/^CEP/)).toHaveValue('96200-000');
  });

  it('F-04: valida na tela, mostra o erro no campo e não chama a API', async () => {
    const fetchMock = mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await fillValidForm(user);
    await user.clear(screen.getByLabelText(/^CPF/));
    await user.type(screen.getByLabelText(/^CPF/), '11111111111');
    await user.clear(screen.getByLabelText(/^Senha/));
    await user.type(screen.getByLabelText(/^Senha/), 'fraca');
    await user.click(screen.getByRole('button', { name: 'Criar conta' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Revise os campos destacados.');
    expect(screen.getByLabelText(/^CPF/)).toHaveAccessibleDescription('CPF inválido.');
    expect(screen.getByLabelText(/^Senha/)).toHaveAccessibleDescription(
      /Use de 8 a 128 caracteres/,
    );
    expect(screen.getByLabelText(/^CPF/)).toHaveFocus();
    expect(registerCalls(fetchMock)).toHaveLength(0);
  });

  it('limpa o erro do campo quando a pessoa o corrige', async () => {
    mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await user.click(screen.getByRole('button', { name: 'Criar conta' }));
    expect(screen.getByLabelText(/Nome completo/)).toHaveAttribute('aria-invalid', 'true');

    await user.type(screen.getByLabelText(/Nome completo/), 'Ana');
    expect(screen.getByLabelText(/Nome completo/)).not.toHaveAttribute('aria-invalid');
  });

  it('F-03: envia os dados sem máscara e leva ao login após 201', async () => {
    const fetchMock = mockApi(() =>
      jsonResponse(201, { id: 'u1', username: 'ana_teste', created_at: '2026-11-14T12:00:00Z' }),
    );
    const user = await renderRegisterPage();

    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Criar conta' }));

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    const [[, options]] = registerCalls(fetchMock);
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({
      full_name: 'Ana Teste',
      username: 'ana_teste',
      email: 'ana@example.com',
      password: 'Senha@123',
      cpf: '52998224725',
      phone: '53999990000',
      cep: '96200000',
      street: 'Rua Exemplo',
      number: '100',
      neighborhood: 'Centro',
      city: 'Rio Grande',
      state: 'RS',
    });
  });

  it.each([
    ['email', /E-mail/, 'Este e-mail já está cadastrado.'],
    ['cpf', /^CPF/, 'Este CPF já está cadastrado.'],
    ['username', /Nome de usuário/, 'Este nome de usuário já está em uso.'],
  ])('F-02 / RN-09: 409 FIELD_IN_USE indica %s em uso', async (field, label, message) => {
    mockApi(() =>
      jsonResponse(409, {
        error: {
          code: 'FIELD_IN_USE',
          message: 'Um dos campos já está em uso.',
          fields: { [field]: 'Este campo já está cadastrado.' },
        },
      }),
    );
    const user = await renderRegisterPage();

    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Criar conta' }));

    const input = screen.getByLabelText(label);
    await vi.waitFor(() => expect(input).toHaveAccessibleDescription(new RegExp(message)));
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveFocus();
    expect(screen.getByRole('heading', { name: 'Criar conta' })).toBeInTheDocument();
  });

  it('mostra no campo os erros 422 vindos da API', async () => {
    mockApi(() =>
      jsonResponse(422, {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Revise os campos informados.',
          fields: { phone: 'Informe um telefone celular com DDD.' },
        },
      }),
    );
    const user = await renderRegisterPage();

    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Criar conta' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Revise os campos informados.');
    expect(screen.getByLabelText(/Telefone celular/)).toHaveAccessibleDescription(
      'Informe um telefone celular com DDD.',
    );
  });

  it('mostra mensagem genérica em erro inesperado, sem detalhes técnicos', async () => {
    mockApi(() => new Response('Internal Server Error', { status: 500 }));
    const user = await renderRegisterPage();

    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Criar conta' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível concluir a ação. Tente novamente.');
    expect(within(alert).queryByText(/Internal Server Error/)).not.toBeInTheDocument();
  });

  it('desabilita o botão enquanto envia', async () => {
    let resolveRegister;
    mockApi(
      () =>
        new Promise((resolve) => {
          resolveRegister = () => resolve(jsonResponse(201, {}));
        }),
    );
    const user = await renderRegisterPage();

    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Criar conta' }));

    expect(await screen.findByRole('button', { name: 'Criando conta…' })).toBeDisabled();
    resolveRegister();
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
  });

  it('tem link para o login', async () => {
    mockApi(() => jsonResponse(201, {}));
    await renderRegisterPage();

    expect(screen.getByRole('link', { name: 'Entrar' })).toHaveAttribute('href', '/login');
  });
});
