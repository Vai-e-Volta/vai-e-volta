import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import FormField from '../src/components/FormField';
import PasswordInput from '../src/components/PasswordInput';

describe('PasswordInput', () => {
  it('mostra e oculta a senha com um botão acessível', async () => {
    const user = userEvent.setup();
    render(
      <FormField label="Senha" required>
        <PasswordInput name="password" defaultValue="Senha@123" />
      </FormField>,
    );

    const input = screen.getByLabelText(/Senha/);
    expect(input).toHaveAttribute('type', 'password');

    const toggle = screen.getByRole('button', { name: 'Mostrar senha' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    await user.click(toggle);

    expect(input).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: 'Ocultar senha' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});
