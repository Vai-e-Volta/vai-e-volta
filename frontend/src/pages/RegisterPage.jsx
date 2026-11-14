import { useMutation } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import FormField, { inputClassName } from '../components/FormField';
import PasswordInput from '../components/PasswordInput';
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

// Etapas do cadastro, com os campos na ordem em que aparecem na tela.
const STEPS = [
  {
    title: 'Dados pessoais',
    description: 'Seu nome, CPF e celular não aparecem no seu perfil.',
    fields: ['full_name', 'cpf', 'phone'],
  },
  {
    title: 'Acesso',
    description: 'Você entra com o e-mail ou com o nome de usuário.',
    fields: ['username', 'email', 'password'],
  },
  {
    title: 'Endereço',
    description: 'Local de retirada dos seus itens. No perfil aparecem só o bairro e a cidade.',
    fields: ['cep', 'street', 'number', 'complement', 'neighborhood', 'city', 'state'],
  },
];

const FIELD_SEQUENCE = STEPS.flatMap((step) => step.fields);
const LAST_STEP = STEPS.length - 1;

const stepOf = (field) => STEPS.findIndex((step) => step.fields.includes(field));

const FIELD_IN_USE_MESSAGES = {
  email: 'Este e-mail já está cadastrado.',
  cpf: 'Este CPF já está cadastrado.',
  username: 'Este nome de usuário já está em uso.',
};

function serverFieldErrors(error) {
  const fields =
    error.code === 'FIELD_IN_USE'
      ? Object.fromEntries(
          Object.entries(error.fields).map(([field, message]) => [
            field,
            FIELD_IN_USE_MESSAGES[field] ?? message,
          ]),
        )
      : error.fields;
  return Object.fromEntries(
    Object.entries(fields).filter(([field]) => field in EMPTY_REGISTRATION),
  );
}

function pick(errors, fields) {
  return Object.fromEntries(Object.entries(errors).filter(([field]) => fields.includes(field)));
}

/** Cadastro (F-01 a F-04): validação na tela como auxílio; a API decide. */
export default function RegisterPage() {
  const navigate = useNavigate();
  const formRef = useRef(null);
  const headingRef = useRef(null);
  const focusTarget = useRef(null);
  const [focusRequest, setFocusRequest] = useState(0);
  const [step, setStep] = useState(0);
  const [values, setValues] = useState(EMPTY_REGISTRATION);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');

  // Move o foco depois que a etapa certa estiver na tela.
  useEffect(() => {
    const target = focusTarget.current;
    if (!target) return;
    focusTarget.current = null;
    if (target === 'heading') headingRef.current?.focus();
    else formRef.current?.elements.namedItem(target)?.focus();
  }, [focusRequest]);

  function requestFocus(target) {
    focusTarget.current = target;
    setFocusRequest((count) => count + 1);
  }

  function showErrors(fieldErrors, message) {
    const first = FIELD_SEQUENCE.find((field) => fieldErrors[field]);
    setErrors(fieldErrors);
    setFormError(message);
    if (first) {
      setStep(stepOf(first));
      requestFocus(first);
    }
  }

  const mutation = useMutation({
    mutationFn: registerUser,
    onSuccess: () => {
      navigate('/login', { replace: true, state: { registered: true } });
    },
    onError: (error) => showErrors(serverFieldErrors(error), error.message),
  });

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

  function goToStep(nextStep) {
    setFormError('');
    setStep(nextStep);
    requestFocus('heading');
  }

  function handleSubmit(event) {
    event.preventDefault();
    const allErrors = validateRegistration(values);

    if (step < LAST_STEP) {
      const stepErrors = pick(allErrors, STEPS[step].fields);
      if (Object.keys(stepErrors).length > 0) {
        showErrors(stepErrors, 'Revise os campos destacados.');
        return;
      }
      setErrors({});
      goToStep(step + 1);
      return;
    }

    if (Object.keys(allErrors).length > 0) {
      showErrors(allErrors, 'Revise os campos destacados.');
      return;
    }
    setFormError('');
    mutation.mutate(toRegistrationPayload(values));
  }

  const fieldProps = (name) => ({
    name,
    value: values[name],
    onChange: handleChange,
    className: inputClassName,
  });

  const current = STEPS[step];

  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
        Crie sua conta
      </h1>
      <p className="mt-2 text-slate-400">
        Uma conta só para anunciar seus itens e alugar os dos outros.
      </p>

      <div className="mt-8 flex gap-2" aria-hidden="true">
        {STEPS.map((item, index) => (
          <span
            key={item.title}
            className={`h-1 flex-1 rounded-full transition-colors ${
              index <= step ? 'bg-accent' : 'bg-line'
            }`}
          />
        ))}
      </div>

      <div className="mt-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Etapa {step + 1} de {STEPS.length}
        </p>
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="mt-1 text-lg font-semibold tracking-tight text-white focus:outline-none"
        >
          {current.title}
        </h2>
        <p className="mt-1 text-sm text-slate-400">{current.description}</p>
      </div>

      {formError && (
        <div
          role="alert"
          className="mt-5 rounded-lg border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-200"
        >
          {formError}
        </div>
      )}

      <form ref={formRef} noValidate onSubmit={handleSubmit} className="mt-6 flex flex-col gap-5">
        {step === 0 && (
          <>
            <FormField label="Nome completo" error={errors.full_name} required>
              <input {...fieldProps('full_name')} autoComplete="name" maxLength={120} />
            </FormField>
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
          </>
        )}

        {step === 1 && (
          <>
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
              <input
                {...fieldProps('email')}
                type="email"
                autoComplete="email"
                placeholder="voce@exemplo.com"
                maxLength={254}
              />
            </FormField>
            <FormField
              label="Senha"
              error={errors.password}
              hint="8 a 128 caracteres, com letra maiúscula, número e caractere especial."
              required
            >
              <PasswordInput
                {...fieldProps('password')}
                autoComplete="new-password"
                maxLength={128}
              />
            </FormField>
          </>
        )}

        {step === 2 && (
          <>
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
            <FormField label="Bairro" error={errors.neighborhood} required>
              <input {...fieldProps('neighborhood')} maxLength={100} />
            </FormField>
            <div className="grid gap-5 sm:grid-cols-[1fr_6rem]">
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
          </>
        )}

        <div className="mt-2 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          {step > 0 ? (
            <button
              type="button"
              onClick={() => goToStep(step - 1)}
              disabled={mutation.isPending}
              className="rounded-lg px-4 py-3 font-medium text-slate-300 hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300 disabled:opacity-60"
            >
              Voltar
            </button>
          ) : (
            <span />
          )}
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-lg bg-accent px-6 py-3 font-semibold text-ink shadow-lg shadow-accent/10 transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
          >
            {step < LAST_STEP ? 'Continuar' : mutation.isPending ? 'Criando conta…' : 'Criar conta'}
          </button>
        </div>
      </form>
    </section>
  );
}
