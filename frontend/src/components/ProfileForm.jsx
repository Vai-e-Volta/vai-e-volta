import { useMutation } from '@tanstack/react-query';
import { useMemo, useRef, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { updateMe } from '../services/me';
import {
  UF_OPTIONS,
  formatCep,
  formatCpf,
  formatPhone,
  profileFromUser,
  serverFieldErrors,
  toProfilePayload,
  validateProfile,
} from '../utils/registrationValidation';
import FormField, { inputClassName } from './FormField';
import { FormMessage, SettingsCard, submitClassName } from './SettingsCard';

const MASKS = { cpf: formatCpf, phone: formatPhone, cep: formatCep };

const FIELD_ORDER = [
  'full_name',
  'username',
  'email',
  'cpf',
  'phone',
  'cep',
  'street',
  'number',
  'complement',
  'neighborhood',
  'city',
  'state',
];

/**
 * Editar dados cadastrais (F-11): mesmas regras do cadastro, sem confirmação por e-mail
 * (RN-16). Envia só os campos alterados; erros da API aparecem em cada campo.
 */
export default function ProfileForm() {
  const { user, refreshSession } = useAuth();
  const initial = useMemo(() => profileFromUser(user), [user]);
  const formRef = useRef(null);
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(null);

  function showErrors(nextErrors, summary) {
    setErrors(nextErrors);
    setMessage({ type: 'error', text: summary });
    const first = FIELD_ORDER.find((field) => nextErrors[field]);
    if (first) formRef.current?.elements.namedItem(first)?.focus();
  }

  const mutation = useMutation({
    mutationFn: updateMe,
    onSuccess: async () => {
      // O usuário da sessão vem de /api/auth/me: busca de novo com os dados salvos.
      await refreshSession();
      setMessage({ type: 'success', text: 'Dados atualizados.' });
    },
    onError: (error) => {
      const fieldErrors = serverFieldErrors(error);
      const summary =
        Object.keys(fieldErrors).length > 0 ? 'Revise os campos destacados.' : error.message;
      showErrors(fieldErrors, error.code === 'FIELD_IN_USE' ? error.message : summary);
    },
  });

  function handleChange(event) {
    const { name, value } = event.target;
    const mask = MASKS[name];
    setValues((current) => ({ ...current, [name]: mask ? mask(value) : value }));
    setMessage(null);
    if (errors[name]) {
      setErrors((current) => {
        const next = { ...current };
        delete next[name];
        return next;
      });
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateProfile(values);
    if (Object.keys(nextErrors).length > 0) {
      showErrors(nextErrors, 'Revise os campos destacados.');
      return;
    }
    setErrors({});
    const changes = toProfilePayload(values, initial);
    if (Object.keys(changes).length === 0) {
      setMessage({ type: 'info', text: 'Nenhuma alteração para salvar.' });
      return;
    }
    setMessage(null);
    mutation.mutate(changes);
  }

  const fieldProps = (name) => ({
    name,
    value: values[name],
    onChange: handleChange,
    className: inputClassName,
  });

  return (
    <SettingsCard
      title="Dados cadastrais"
      description="Nome completo, CPF, telefone e endereço completo não aparecem no seu perfil público."
    >
      <FormMessage message={message} />
      <form ref={formRef} noValidate onSubmit={handleSubmit} className="mt-5 flex flex-col gap-5">
        <FormField label="Nome completo" error={errors.full_name} required>
          <input {...fieldProps('full_name')} autoComplete="name" maxLength={120} />
        </FormField>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            label="Nome de usuário"
            error={errors.username}
            hint="3 a 30 caracteres: letras minúsculas, números e _."
            required
          >
            <input
              {...fieldProps('username')}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={30}
            />
          </FormField>
          <FormField label="E-mail" error={errors.email} required>
            <input {...fieldProps('email')} type="email" autoComplete="email" maxLength={254} />
          </FormField>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label="CPF" error={errors.cpf} required>
            <input
              {...fieldProps('cpf')}
              inputMode="numeric"
              placeholder="000.000.000-00"
              autoComplete="off"
            />
          </FormField>
          <FormField label="Telefone celular" error={errors.phone} required>
            <input
              {...fieldProps('phone')}
              type="tel"
              inputMode="numeric"
              placeholder="(00) 00000-0000"
              autoComplete="tel-national"
            />
          </FormField>
        </div>
        <div className="grid gap-5 sm:grid-cols-[10rem_1fr]">
          <FormField label="CEP" error={errors.cep} required>
            <input
              {...fieldProps('cep')}
              inputMode="numeric"
              placeholder="00000-000"
              autoComplete="postal-code"
            />
          </FormField>
          <FormField label="Rua" error={errors.street} required>
            <input {...fieldProps('street')} autoComplete="address-line1" maxLength={100} />
          </FormField>
        </div>
        <div className="grid gap-5 sm:grid-cols-[8rem_1fr]">
          <FormField label="Número" error={errors.number} required>
            <input {...fieldProps('number')} maxLength={10} />
          </FormField>
          <FormField label="Complemento" error={errors.complement}>
            <input {...fieldProps('complement')} autoComplete="address-line2" maxLength={60} />
          </FormField>
        </div>
        <div className="grid gap-5 sm:grid-cols-[1fr_1fr_6rem]">
          <FormField label="Bairro" error={errors.neighborhood} required>
            <input {...fieldProps('neighborhood')} maxLength={100} />
          </FormField>
          <FormField label="Cidade" error={errors.city} required>
            <input {...fieldProps('city')} autoComplete="address-level2" maxLength={100} />
          </FormField>
          <FormField label="UF" error={errors.state} required>
            <select {...fieldProps('state')} autoComplete="address-level1">
              <option value="">--</option>
              {UF_OPTIONS.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
          </FormField>
        </div>
        <div className="flex justify-end">
          <button type="submit" disabled={mutation.isPending} className={submitClassName}>
            {mutation.isPending ? 'Salvando…' : 'Salvar dados'}
          </button>
        </div>
      </form>
    </SettingsCard>
  );
}
