import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

function mockAnonymous() {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Faça login.' } }),
  );
}

describe('abas de acesso', () => {
  it('as abas seguem o padrão tablist e marcam a rota atual', async () => {
    mockAnonymous();
    renderWithProviders(<AppRoutes />, { route: '/cadastro' });
    await screen.findByRole('heading', { name: 'Crie sua conta' });

    expect(screen.getByRole('tablist', { name: 'Acesso à conta' })).toBeInTheDocument();
    const login = screen.getByRole('tab', { name: 'Entrar' });
    const register = screen.getByRole('tab', { name: 'Criar conta' });
    expect(register).toHaveAttribute('aria-selected', 'true');
    expect(login).toHaveAttribute('aria-selected', 'false');
    expect(login).toHaveAttribute('href', '/login');
    expect(register).toHaveAttribute('tabindex', '0');
    expect(login).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('tabpanel')).toHaveAccessibleName('Criar conta');
  });

  it('clicar na aba troca para a rota correspondente', async () => {
    mockAnonymous();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/login' });
    await screen.findByRole('heading', { name: 'Entrar' });

    await user.click(screen.getByRole('tab', { name: 'Criar conta' }));

    expect(await screen.findByRole('heading', { name: 'Crie sua conta' })).toBeInTheDocument();
  });

  it('setas do teclado trocam de aba e movem o foco', async () => {
    mockAnonymous();
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: '/login' });
    await screen.findByRole('heading', { name: 'Entrar' });

    screen.getByRole('tab', { name: 'Entrar' }).focus();
    await user.keyboard('{ArrowRight}');

    expect(await screen.findByRole('heading', { name: 'Crie sua conta' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Criar conta' })).toHaveFocus();

    await user.keyboard('{ArrowLeft}');
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Entrar' })).toHaveFocus();
  });
});
