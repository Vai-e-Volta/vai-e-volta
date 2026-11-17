import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

// Dados fictícios.
const ME = { id: 'u1', username: 'ana_teste', full_name: 'Ana Teste', state: 'RS' };

function mockApi(deleteResponse) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options = {}) => {
    if (url === '/api/auth/me') return jsonResponse(200, ME);
    if (url === '/api/me' && options.method === 'DELETE') return deleteResponse();
    throw new Error(`URL inesperada: ${options.method} ${url}`);
  });
}

const deleteCalls = (fetchMock) =>
  fetchMock.mock.calls.filter(
    ([url, options]) => url === '/api/me' && options?.method === 'DELETE',
  );

async function openDeleteDialog() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/configuracoes' });
  const section = await screen.findByRole('region', { name: 'Excluir conta' });
  await user.click(within(section).getByRole('button', { name: 'Excluir conta' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Excluir sua conta?' });
  return { user, section, dialog };
}

describe('configurações: excluir conta (F-13)', () => {
  it('avisa o que acontece e pede a senha antes de chamar a API', async () => {
    const fetchMock = mockApi(() => new Response(null, { status: 204 }));
    const { user, section, dialog } = await openDeleteDialog();

    expect(section).toHaveTextContent('Seus anúncios ficam pausados');
    expect(section).toHaveTextContent('Seus dados ficam guardados por 1 ano');
    expect(within(dialog).getByLabelText(/Sua senha/)).toHaveFocus();

    await user.click(within(dialog).getByRole('button', { name: 'Excluir conta' }));

    expect(within(dialog).getByLabelText(/Sua senha/)).toHaveAccessibleDescription(
      'Informe sua senha para confirmar.',
    );
    expect(deleteCalls(fetchMock)).toHaveLength(0);
  });

  it('RN-16: senha incorreta (401) mostra o erro no campo e mantém a sessão', async () => {
    mockApi(() =>
      jsonResponse(401, { error: { code: 'INVALID_CREDENTIALS', message: 'Credenciais.' } }),
    );
    const { user, dialog } = await openDeleteDialog();

    await user.type(within(dialog).getByLabelText(/Sua senha/), 'Errada@123{Enter}');

    await waitFor(() =>
      expect(within(dialog).getByLabelText(/Sua senha/)).toHaveAccessibleDescription(
        'Senha incorreta.',
      ),
    );
    expect(within(dialog).getByLabelText(/Sua senha/)).toHaveValue('');
    expect(screen.getByRole('heading', { name: 'Configurações', level: 1 })).toBeInTheDocument();
  });

  it('RN-18: 409 ACCOUNT_HAS_ACTIVE_RENTAL fecha o diálogo e explica o motivo', async () => {
    mockApi(() =>
      jsonResponse(409, {
        error: { code: 'ACCOUNT_HAS_ACTIVE_RENTAL', message: 'Há aluguel ativo.' },
      }),
    );
    const { user, section, dialog } = await openDeleteDialog();

    await user.type(within(dialog).getByLabelText(/Sua senha/), 'Senha@123');
    await user.click(within(dialog).getByRole('button', { name: 'Excluir conta' }));

    const alert = await within(section).findByRole('alert');
    expect(alert).toHaveTextContent('aluguel aceito em andamento ou agendado');
    expect(within(alert).getByRole('link', { name: 'Ver meus aluguéis' })).toHaveAttribute(
      'href',
      '/alugueis',
    );
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(within(section).getByRole('button', { name: 'Excluir conta' })).toHaveFocus();
  });

  it('com 204 envia a senha, encerra a sessão e leva ao login com aviso', async () => {
    const fetchMock = mockApi(() => new Response(null, { status: 204 }));
    const { user, dialog } = await openDeleteDialog();

    await user.type(within(dialog).getByLabelText(/Sua senha/), 'Senha@123');
    await user.click(within(dialog).getByRole('button', { name: 'Excluir conta' }));

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Que bom te ver de novo!' })).toBeInTheDocument(),
    );
    expect(screen.getByRole('status')).toHaveTextContent('Sua conta foi excluída.');
    const [[, options]] = deleteCalls(fetchMock);
    expect(JSON.parse(options.body)).toEqual({ password: 'Senha@123' });
  });
});
