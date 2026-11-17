import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

const USER = { id: 'u1', username: 'ana_teste' };

/** Simula a API: sem sessão até o login dar certo. */
function mockApi(loginResponse) {
  let loggedIn = false;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') {
      return loggedIn
        ? jsonResponse(200, USER)
        : jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Faça login.' } });
    }
    if (url === '/api/auth/login') {
      const response = loginResponse();
      if (response.ok) loggedIn = true;
      return response;
    }
    throw new Error(`URL inesperada: ${url}`);
  });
}

async function renderLogin(route = '/login') {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route });
  await screen.findByRole('heading', { name: 'Que bom te ver de novo!' });
  return user;
}

async function fillAndSubmit(user, identifier = 'ana_teste', password = 'Senha@123') {
  await user.type(screen.getByLabelText(/E-mail ou nome de usuário/), identifier);
  await user.type(screen.getByLabelText(/^Senha/), password);
  await user.click(screen.getByRole('button', { name: 'Entrar' }));
}

describe('tela de login (H-002)', () => {
  it('F-05: aceita e-mail ou usuário e envia identifier e password', async () => {
    const fetchMock = mockApi(() => jsonResponse(200, USER));
    const user = await renderLogin();

    await fillAndSubmit(user, '  ana_teste ');

    expect(await screen.findByRole('heading', { name: 'Itens para alugar' })).toBeInTheDocument();
    const [, options] = fetchMock.mock.calls.find(([url]) => url === '/api/auth/login');
    expect(JSON.parse(options.body)).toEqual({ identifier: 'ana_teste', password: 'Senha@123' });
  });

  it('após o login volta à rota privada que a pessoa tentou abrir', async () => {
    mockApi(() => jsonResponse(200, USER));
    const user = await renderLogin('/alugueis');

    await fillAndSubmit(user);

    expect(await screen.findByRole('heading', { name: 'Aluguéis' })).toBeInTheDocument();
  });

  it('F-06 / RN-12: mostra a mensagem única da API, limpa a senha e continua no login', async () => {
    mockApi(() =>
      jsonResponse(401, {
        error: { code: 'INVALID_CREDENTIALS', message: 'E-mail, usuário ou senha incorretos.' },
      }),
    );
    const user = await renderLogin();

    await fillAndSubmit(user);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'E-mail, usuário ou senha incorretos.',
    );
    expect(screen.getByLabelText(/^Senha/)).toHaveValue('');
    expect(screen.getByLabelText(/^Senha/)).toHaveFocus();
    expect(screen.getByRole('heading', { name: 'Que bom te ver de novo!' })).toBeInTheDocument();
  });

  it('RN-14: no bloqueio (429) mostra quanto falta usando o Retry-After', async () => {
    mockApi(
      () =>
        new Response(
          JSON.stringify({ error: { code: 'LOGIN_LOCKED', message: 'Muitas tentativas.' } }),
          { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '840' } },
        ),
    );
    const user = await renderLogin();

    await fillAndSubmit(user);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Muitas tentativas de login. Tente de novo em 14 minutos.',
    );
  });

  it('RN-14: sem Retry-After, o bloqueio ainda mostra uma mensagem clara', async () => {
    mockApi(() =>
      jsonResponse(429, { error: { code: 'LOGIN_LOCKED', message: 'Muitas tentativas.' } }),
    );
    const user = await renderLogin();

    await fillAndSubmit(user);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Muitas tentativas de login. Aguarde alguns minutos e tente de novo.',
    );
  });

  it('campos vazios mostram erro sem chamar a API', async () => {
    const fetchMock = mockApi(() => jsonResponse(200, USER));
    const user = await renderLogin();

    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(screen.getByLabelText(/E-mail ou nome de usuário/)).toHaveAccessibleDescription(
      'Campo obrigatório.',
    );
    expect(screen.getByLabelText(/E-mail ou nome de usuário/)).toHaveFocus();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/auth/login')).toBe(false);
  });
});
