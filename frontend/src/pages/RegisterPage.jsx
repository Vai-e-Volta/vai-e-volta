import { useMutation } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import FormField, { inputClassName } from '../components/FormField';
import { registerUser } from '../services/auth';
import {
  EMPTY_REGISTRATION,
  UF_OPTIONS,
  formatCep,
  formatCpf,
  formatPhone,
  toRegistrationPayload,
  validateRegistration,
} from '../utils/registrationValidation';

const MASKS = { cpf: formatCpf, phone: formatPhone, cep: formatCep };

const FIELD_IN_USE_MESSAGES = {
  email: 'Este e-mail já está cadastrado.',
  cpf: 'Este CPF já está cadastrado.',
  username: 'Este nome de usuário já está em uso.',
};

function serverFieldErrors(error) {
  if (error.code === 'FIELD_IN_USE') {
    return Object.fromEntries(
      Object.entries(error.fields).map(([field, message]) => [
        field,
        FIELD_IN_USE_MESSAGES[field] ?? message,
      ]),
    );
  }
  return error.fields;
}

/** Cadastro (F-01 a F-04): validação na tela como auxílio; a API decide. */
export default function RegisterPage() {
  const navigate = useNavigate();
  const formRef = useRef(null);
  const [values, setValues] = useState(EMPTY_REGISTRATION);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');

  const mutation = useMutation({
    mutationFn: registerUser,
    onSuccess: () => {
      navigate('/login', { replace: true, state: { registered: true } });
    },
    onError: (error) => {
      const fields = serverFieldErrors(error);
      const knownFields = Object.fromEntries(
        Object.entries(fields).filter(([field]) => field in EMPTY_REGISTRATION),
      );
      setErrors(knownFields);
      setFormError(error.message);
      focusFirstError(knownFields);
    },
  });

  // Foca o primeiro campo com erro na ordem em que aparece na tela.
  function focusFirstError(fieldErrors) {
    const elements = Array.from(formRef.current?.elements ?? []);
    elements.find((element) => fieldErrors[element.name])?.focus();
  }

  function handleChange(event) {
    const { name, value } = event.target;
    const mask = MASKS[name];
    setValues((current) => ({ ...current, [name]: mask ? mask(value) : value }));
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
    setFormError('');
    const clientErrors = validateRegistration(values);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) {
      setFormError('Revise os campos destacados.');
      focusFirstError(clientErrors);
      return;
    }
    mutation.mutate(toRegistrationPayload(values));
  }

  const fieldProps = (name) => ({
    name,
    value: values[name],
    onChange: handleChange,
    className: inputClassName,
  });

  return (
    <section className="mx-auto w-full max-w-2xl">
      <h1 className="text-2xl font-bold text-slate-900">Criar conta</h1>
      <p className="mt-1 text-slate-700">
        Já tem conta?{' '}
        <Link
          to="/login"
          className="font-medium text-emerald-800 underline hover:text-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
        >
          Entrar
        </Link>
      </p>

      {formError && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-red-800"
        >
          {formError}
        </div>
      )}

      <form ref={formRef} noValidate onSubmit={handleSubmit} className="mt-6 flex flex-col gap-8">
        <fieldset className="grid gap-4">
          <legend className="mb-2 text-lg font-semibold text-slate-900">Dados pessoais</legend>
          <FormField label="Nome completo" error={errors.full_name} required>
            <input {...fieldProps('full_name')} autoComplete="name" maxLength={120} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
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
        </fieldset>

        <fieldset className="grid gap-4">
          <legend className="mb-2 text-lg font-semibold text-slate-900">Acesso</legend>
          <div className="grid gap-4 sm:grid-cols-2">
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
          <FormField
            label="Senha"
            error={errors.password}
            hint="8 a 128 caracteres, com letra maiúscula, número e caractere especial."
            required
          >
            <input
              {...fieldProps('password')}
              type="password"
              autoComplete="new-password"
              maxLength={128}
            />
          </FormField>
        </fieldset>

        <fieldset className="grid gap-4">
          <legend className="mb-2 text-lg font-semibold text-slate-900">Endereço</legend>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="CEP" error={errors.cep} required>
              <input
                {...fieldProps('cep')}
                inputMode="numeric"
                placeholder="00000-000"
                autoComplete="postal-code"
              />
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
            <FormField label="Rua" error={errors.street} required>
              <input {...fieldProps('street')} autoComplete="address-line1" maxLength={100} />
            </FormField>
            <FormField label="Número" error={errors.number} required>
              <input {...fieldProps('number')} maxLength={10} />
            </FormField>
          </div>
          <FormField label="Complemento" error={errors.complement}>
            <input {...fieldProps('complement')} autoComplete="address-line2" maxLength={60} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-[1fr_1fr_6rem]">
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
        </fieldset>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full rounded-md bg-emerald-700 px-4 py-3 text-base font-semibold text-white hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:opacity-60 sm:w-auto sm:self-end"
        >
          {mutation.isPending ? 'Criando conta…' : 'Criar conta'}
        </button>
      </form>
    </section>
  );
}
