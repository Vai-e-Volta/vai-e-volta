import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ConfirmDialog from '../src/components/ConfirmDialog';

function renderDialog(props = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ConfirmDialog
      open
      title="Excluir anúncio?"
      description="Essa ação não pode ser desfeita."
      confirmLabel="Excluir"
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onConfirm, onCancel };
}

describe('ConfirmDialog', () => {
  it('não renderiza quando fechado', () => {
    render(<ConfirmDialog open={false} title="X" onConfirm={() => {}} onCancel={() => {}} />);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('é acessível e foca o botão de cancelar', () => {
    renderDialog();

    const dialog = screen.getByRole('alertdialog', { name: 'Excluir anúncio?' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleDescription('Essa ação não pode ser desfeita.');
    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus();
  });

  it('confirma e cancela pelos botões', async () => {
    const user = userEvent.setup();
    const { onConfirm, onCancel } = renderDialog();

    await user.click(screen.getByRole('button', { name: 'Excluir' }));
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('Esc cancela e Tab circula dentro do diálogo', async () => {
    const user = userEvent.setup();
    const { onCancel } = renderDialog();

    await user.tab();
    expect(screen.getByRole('button', { name: 'Excluir' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Excluir' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('desabilita os botões enquanto ocupado', () => {
    renderDialog({ busy: true });

    expect(screen.getByRole('button', { name: 'Excluir' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled();
  });
});

describe('ConfirmDialog com campos', () => {
  it('foca o primeiro campo e Enter confirma', async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmDialog open title="Confirmar?" onConfirm={onConfirm} onCancel={() => {}}>
        <label>
          Senha
          <input type="password" />
        </label>
      </ConfirmDialog>,
    );

    expect(screen.getByLabelText('Senha')).toHaveFocus();
    await user.keyboard('abc{Enter}');

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
