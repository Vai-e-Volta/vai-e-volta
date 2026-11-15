import { useMutation } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { useLocation } from 'react-router';
import FormField, { inputClassName } from '../components/FormField';
import PasswordInput from '../components/PasswordInput';
import { useAuth } from '../hooks/useAuth';
import { login } from '../services/auth';

const EMPTY = { identifier: '', password: '' };

/** Mensagem de bloqueio (RN-14) com o tempo do Retry-After, arredondado para minutos. */
function lockedMessage(retryAfter) {
  if (!retryAfter) return 'Muitas tentativas de login. Aguarde alguns minutos e tente de novo.';
  const minutes = Math.max(1, Math.ceil(retryAfter / 60));
  const unit = minutes === 1 ? 'minuto' : 'minutos';
  return `Muitas tentativas de login. Tente de novo em ${minutes} ${unit}.`;
}

/**
 * Login (F-05 a F-07): e-mail ou nome de usuário e senha. A mensagem de credencial
 * incorreta vem da API e é única (RN-12); o bloqueio por tentativas responde 429 com
 * Retry-After (RN-14).
 */
export default function LoginPage() {
  const location = useLocation();
  const { refreshSession } = useAuth();
  const formRef = useRef(null);
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const registered = location.state?.registered === true;

  const mutation = useMutation({
    mutationFn: login,
    // Com a sessão carregada, a rota pública leva ao destino guardado ou a /.
    onSuccess: () => refreshSession(),
    onError: (error) => {
      setFormError(error.status === 429 ? lockedMessage(error.retryAfter) : error.message);
      setValues((current) => ({ ...current, password: '' }));
      formRef.current?.elements.namedItem('password')?.focus();
    },
  });

  function handleChange(event) {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    if (errors[name]) setErrors((current) => ({ ...current, [name]: undefined }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = {};
    if (!values.identifier.trim()) nextErrors.identifier = 'Campo obrigatório.';
    if (!values.password) nextErrors.password = 'Campo obrigatório.';
    setErrors(nextErrors);
    const first = ['identifier', 'password'].find((field) => nextErrors[field]);
    if (first) {
      setFormError('');
      formRef.current?.elements.namedItem(first)?.focus();
      return;
    }
    setFormError('');
    mutation.mutate({ identifier: values.identifier.trim(), password: values.password });
  }

  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
        Que bom te ver de novo!
      </h1>
      <p className="mt-2 text-slate-400">Entre para ver seus aluguéis, anúncios e propostas.</p>

      {registered && !formError && (
        <div
          role="status"
          className="mt-6 rounded-lg border border-flow/30 bg-flow/10 px-4 py-3 text-sm text-teal-100"
        >
          Conta criada! Agora é só entrar com seus dados.
        </div>
      )}

      {formError && (
        <div
          role="alert"
          className="mt-6 rounded-lg border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-200"
        >
          {formError}
        </div>
      )}

      <form ref={formRef} noValidate onSubmit={handleSubmit} className="mt-8 flex flex-col gap-5">
        <FormField label="E-mail ou nome de usuário" error={errors.identifier} required>
          <input
            name="identifier"
            value={values.identifier}
            onChange={handleChange}
            className={inputClassName}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="voce@exemplo.com"
          />
        </FormField>
        <FormField label="Senha" error={errors.password} required>
          <PasswordInput
            name="password"
            value={values.password}
            onChange={handleChange}
            autoComplete="current-password"
            maxLength={128}
          />
        </FormField>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="mt-2 rounded-lg bg-accent px-6 py-3 font-semibold text-ink shadow-lg shadow-accent/10 transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
        >
          {mutation.isPending ? 'Entrando…' : 'Entrar'}
        </button>
        <p className="text-center text-sm text-slate-400">
          Você continua conectado por 15 dias neste navegador.
        </p>
      </form>
    </section>
  );
}
