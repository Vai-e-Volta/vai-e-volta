import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import FormField from '../src/components/FormField';

describe('FormField', () => {
  it('associa rótulo ao campo', () => {
    render(
      <FormField label="E-mail" required>
        <input type="email" />
      </FormField>,
    );

    const input = screen.getByLabelText(/E-mail/);
    expect(input).toBeRequired();
    expect(input).not.toHaveAttribute('aria-invalid');
  });

  it('associa a mensagem de erro ao campo', () => {
    render(
      <FormField label="CPF" error="CPF inválido." required>
        <input />
      </FormField>,
    );

    const input = screen.getByLabelText(/CPF/);
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('CPF inválido.');
  });

  it('mantém o id informado e inclui a dica na descrição', () => {
    render(
      <FormField label="Complemento" hint="Ex.: apto 101">
        <input id="complement" />
      </FormField>,
    );

    const input = screen.getByLabelText(/Complemento/);
    expect(input).toHaveAttribute('id', 'complement');
    expect(input).not.toBeRequired();
    expect(input).toHaveAccessibleDescription('Ex.: apto 101');
    expect(screen.getByText('(opcional)')).toBeInTheDocument();
  });
});
