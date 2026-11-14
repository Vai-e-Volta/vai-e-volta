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
  await screen.findByRole('heading', { name: 'Crie sua conta' });
  return user;
}

const next = (user) => user.click(screen.getByRole('button', { name: 'Continuar' }));
const submit = (user) => user.click(screen.getByRole('button', { name: 'Criar conta' }));

// Dados fictícios.
async function fillPersonal(user) {
  await user.type(screen.getByLabelText(/Nome completo/), 'Ana Teste');
  await user.type(screen.getByLabelText(/^CPF/), '52998224725');
  await user.type(screen.getByLabelText(/Telefone celular/), '53999990000');
}

async function fillAccess(user) {
  await user.type(screen.getByLabelText(/Nome de usuário/), 'ana_teste');
  await user.type(screen.getByLabelText(/E-mail/), 'ana@example.com');
  await user.type(screen.getByLabelText(/^Senha/), 'Senha@123');
}

async function fillAddress(user) {
  await user.type(screen.getByLabelText(/^CEP/), '96200000');
  await user.type(screen.getByLabelText(/^Rua/), 'Rua Exemplo');
  await user.type(screen.getByLabelText(/^Número/), '100');
  await user.type(screen.getByLabelText(/^Bairro/), 'Centro');
  await user.type(screen.getByLabelText(/^Cidade/), 'Rio Grande');
  await user.selectOptions(screen.getByLabelText(/^UF/), 'RS');
}

async function fillAll(user) {
  await fillPersonal(user);
  await next(user);
  await fillAccess(user);
  await next(user);
  await fillAddress(user);
}

describe('tela de cadastro (H-001)', () => {
  it('F-01: as etapas mostram todos os campos do contrato, com complemento opcional', async () => {
    mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    expect(screen.getByRole('heading', { name: 'Dados pessoais' })).toBeInTheDocument();
    for (const label of [/Nome completo/, /^CPF/, /Telefone celular/]) {
      expect(screen.getByLabelText(label)).toBeRequired();
    }

    await fillPersonal(user);
    await next(user);
    expect(screen.getByRole('heading', { name: 'Acesso' })).toHaveFocus();
    for (const label of [/Nome de usuário/, /E-mail/, /^Senha/]) {
      expect(screen.getByLabelText(label)).toBeRequired();
    }
    expect(screen.getByLabelText(/^Senha/)).toHaveAttribute('type', 'password');

    await fillAccess(user);
    await next(user);
    expect(screen.getByRole('heading', { name: 'Endereço' })).toBeInTheDocument();
    for (const label of [/^CEP/, /^Rua/, /^Número/, /^Bairro/, /^Cidade/, /^UF/]) {
      expect(screen.getByLabelText(label)).toBeRequired();
    }
    expect(screen.getByLabelText(/Complemento/)).not.toBeRequired();
  });

  it('aplica máscara de CPF, telefone e CEP', async () => {
    mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await fillPersonal(user);
    expect(screen.getByLabelText(/^CPF/)).toHaveValue('529.982.247-25');
    expect(screen.getByLabelText(/Telefone celular/)).toHaveValue('(53) 99999-0000');

    await next(user);
    await fillAccess(user);
    await next(user);
    await user.type(screen.getByLabelText(/^CEP/), '96200000');
    expect(screen.getByLabelText(/^CEP/)).toHaveValue('96200-000');
  });

  it('F-04: não avança com erro na etapa, mostra o erro no campo e não chama a API', async () => {
    const fetchMock = mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await user.type(screen.getByLabelText(/Nome completo/), 'Ana Teste');
    await user.type(screen.getByLabelText(/^CPF/), '11111111111');
    await next(user);

    expect(screen.getByRole('heading', { name: 'Dados pessoais' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Revise os campos destacados.');
    expect(screen.getByLabelText(/^CPF/)).toHaveAccessibleDescription('CPF inválido.');
    expect(screen.getByLabelText(/^CPF/)).toHaveFocus();
    expect(screen.getByLabelText(/Telefone celular/)).toHaveAccessibleDescription(
      'Campo obrigatório.',
    );
    expect(registerCalls(fetchMock)).toHaveLength(0);
  });

  it('valida a senha na etapa de acesso', async () => {
    mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await fillPersonal(user);
    await next(user);
    await user.type(screen.getByLabelText(/Nome de usuário/), 'ana_teste');
    await user.type(screen.getByLabelText(/E-mail/), 'ana@example.com');
    await user.type(screen.getByLabelText(/^Senha/), 'fraca');
    await next(user);

    expect(screen.getByLabelText(/^Senha/)).toHaveAccessibleDescription(
      /Use de 8 a 128 caracteres/,
    );
    expect(screen.getByLabelText(/^Senha/)).toHaveFocus();
  });

  it('Voltar mantém os dados já preenchidos', async () => {
    mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await fillPersonal(user);
    await next(user);
    await user.click(screen.getByRole('button', { name: 'Voltar' }));

    expect(screen.getByRole('heading', { name: 'Dados pessoais' })).toHaveFocus();
    expect(screen.getByLabelText(/Nome completo/)).toHaveValue('Ana Teste');
  });

  it('limpa o erro do campo quando a pessoa o corrige', async () => {
    mockApi(() => jsonResponse(201, {}));
    const user = await renderRegisterPage();

    await next(user);
    expect(screen.getByLabelText(/Nome completo/)).toHaveAttribute('aria-invalid', 'true');

    await user.type(screen.getByLabelText(/Nome completo/), 'Ana');
    expect(screen.getByLabelText(/Nome completo/)).not.toHaveAttribute('aria-invalid');
  });

  it('F-03: envia os dados sem máscara e leva ao login após 201', async () => {
    const fetchMock = mockApi(() =>
      jsonResponse(201, { id: 'u1', username: 'ana_teste', created_at: '2026-11-14T12:00:00Z' }),
    );
    const user = await renderRegisterPage();

    await fillAll(user);
    await submit(user);

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
    ['email', /E-mail/, 'Acesso', 'Este e-mail já está cadastrado.'],
    ['cpf', /^CPF/, 'Dados pessoais', 'Este CPF já está cadastrado.'],
    ['username', /Nome de usuário/, 'Acesso', 'Este nome de usuário já está em uso.'],
  ])(
    'F-02 / RN-09: 409 FIELD_IN_USE volta à etapa e indica %s em uso',
    async (field, label, stepTitle, message) => {
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

      await fillAll(user);
      await submit(user);

      expect(await screen.findByRole('heading', { name: stepTitle })).toBeInTheDocument();
      const input = screen.getByLabelText(label);
      expect(input).toHaveAccessibleDescription(new RegExp(message));
      expect(input).toHaveAttribute('aria-invalid', 'true');
      await vi.waitFor(() => expect(input).toHaveFocus());
    },
  );

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

    await fillAll(user);
    await submit(user);

    expect(await screen.findByRole('alert')).toHaveTextContent('Revise os campos informados.');
    expect(screen.getByLabelText(/Telefone celular/)).toHaveAccessibleDescription(
      'Informe um telefone celular com DDD.',
    );
  });

  it('mostra mensagem genérica em erro inesperado, sem detalhes técnicos', async () => {
    mockApi(() => new Response('Internal Server Error', { status: 500 }));
    const user = await renderRegisterPage();

    await fillAll(user);
    await submit(user);

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

    await fillAll(user);
    await submit(user);

    expect(await screen.findByRole('button', { name: 'Criando conta…' })).toBeDisabled();
    resolveRegister();
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
  });
});
