import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AppRoutes from '../src/AppRoutes';
import { jsonResponse, renderWithProviders } from './renderWithProviders';

const PROFILE = {
  username: 'ana_teste',
  neighborhood: 'Centro',
  city: 'Rio Grande',
  created_at: '2026-10-10T12:00:00Z',
  listings: [],
};

function mockApi() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (url === '/api/auth/me') return jsonResponse(200, { id: 'u1', username: 'ana_teste' });
    if (url === '/api/users/ana_teste') return jsonResponse(200, PROFILE);
    if (url === '/api/auth/logout') return new Response(null, { status: 204 });
    return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Não encontrado.' } });
  });
}

async function renderFeed() {
  const user = userEvent.setup();
  renderWithProviders(<AppRoutes />, { route: '/' });
  await screen.findByRole('heading', { name: 'Itens para alugar' });
  return { user, button: screen.getByRole('button', { name: 'Menu da conta de ana_teste' }) };
}

describe('menu do perfil (F-09)', () => {
  it('abre com Perfil, Configurações e Sair', async () => {
    mockApi();
    const { user, button } = await renderFeed();
    expect(button).toHaveAttribute('aria-expanded', 'false');

    await user.click(button);

    expect(button).toHaveAttribute('aria-expanded', 'true');
    const items = screen.getAllByRole('menuitem').map((item) => item.textContent);
    expect(items).toEqual(['Perfil', 'Configurações', 'Meus anúncios', 'Sair']);
    expect(screen.getByRole('menuitem', { name: 'Perfil' })).toHaveFocus();
  });

  it('funciona pelo teclado: setas, Home, End e Esc devolve o foco ao botão', async () => {
    mockApi();
    const { user, button } = await renderFeed();
    button.focus();

    await user.keyboard('{ArrowUp}');
    expect(screen.getByRole('menuitem', { name: 'Sair' })).toHaveFocus();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Perfil' })).toHaveFocus();
    await user.keyboard('{End}');
    expect(screen.getByRole('menuitem', { name: 'Sair' })).toHaveFocus();
    await user.keyboard('{Home}');
    expect(screen.getByRole('menuitem', { name: 'Perfil' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(button).toHaveFocus();
  });

  it('Enter em Configurações leva a /configuracoes', async () => {
    mockApi();
    const { user, button } = await renderFeed();
    button.focus();

    await user.keyboard('{Enter}');
    await user.keyboard('{ArrowDown}{Enter}');

    expect(await screen.findByRole('heading', { name: 'Configurações' })).toBeInTheDocument();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('Perfil leva ao perfil público da própria pessoa', async () => {
    mockApi();
    const { user, button } = await renderFeed();

    await user.click(button);
    await user.click(screen.getByRole('menuitem', { name: 'Perfil' }));

    expect(await screen.findByRole('heading', { name: '@ana_teste' })).toBeInTheDocument();
  });

  it('Meus anúncios abre a visão do anunciante', async () => {
    mockApi();
    const { user, button } = await renderFeed();
    await user.click(button);
    await user.click(screen.getByRole('menuitem', { name: 'Meus anúncios' }));
    expect(await screen.findByRole('tab', { name: 'Meus anúncios' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('fecha ao clicar fora', async () => {
    mockApi();
    const { user, button } = await renderFeed();

    await user.click(button);
    await user.click(screen.getByRole('heading', { name: 'Itens para alugar' }));

    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
