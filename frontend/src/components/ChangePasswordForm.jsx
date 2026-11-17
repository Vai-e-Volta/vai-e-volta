import { useMutation } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { changePassword } from '../services/me';
import { isValidPassword } from '../utils/registrationValidation';
import FormField from './FormField';
import PasswordInput from './PasswordInput';
import { FormMessage, SettingsCard, submitClassName } from './SettingsCard';

const EMPTY = { current_password: '', new_password: '' };
const FIELD_ORDER = ['current_password', 'new_password'];

/**
 * Trocar a senha (F-12): exige a senha atual (RN-16); a nova segue a RN-04. A API
 * mantém esta sessão e encerra as demais.
 */
export default function ChangePasswordForm() {
  const formRef = useRef(null);
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(null);

  function showErrors(nextErrors, summary) {
    setErrors(nextErrors);
    setMessage({ type: 'error', text: summary });
    const first = FIELD_ORDER.find((field) => nextErrors[field]);
    if (first) formRef.current?.elements.namedItem(first)?.focus();
  }

  const mutation = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      setValues(EMPTY);
      setMessage({
        type: 'success',
        text: 'Senha alterada. Você continua conectado aqui; outras sessões foram encerradas.',
      });
    },
    onError: (error) => {
      if (error.status === 401) {
        setValues((current) => ({ ...current, current_password: '' }));
        showErrors({ current_password: 'Senha atual incorreta.' }, 'A senha atual está incorreta.');
        return;
      }
      const fieldErrors = Object.fromEntries(
        Object.entries(error.fields).filter(([field]) => FIELD_ORDER.includes(field)),
      );
      showErrors(
        fieldErrors,
        Object.keys(fieldErrors).length > 0 ? 'Revise os campos destacados.' : error.message,
      );
    },
  });

  function handleChange(event) {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setMessage(null);
    if (errors[name]) setErrors((current) => ({ ...current, [name]: undefined }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = {};
    if (!values.current_password) nextErrors.current_password = 'Campo obrigatório.';
    if (!values.new_password) nextErrors.new_password = 'Campo obrigatório.';
    else if (!isValidPassword(values.new_password)) {
      nextErrors.new_password = 'Use de 8 a 128 caracteres, com maiúscula, número e símbolo.';
    }
    if (Object.keys(nextErrors).length > 0) {
      showErrors(nextErrors, 'Revise os campos destacados.');
      return;
    }
    setErrors({});
    setMessage(null);
    mutation.mutate({
      currentPassword: values.current_password,
      newPassword: values.new_password,
    });
  }

  return (
    <SettingsCard title="Trocar senha" description="Para trocar, confirme a senha atual.">
      <FormMessage message={message} />
      <form ref={formRef} noValidate onSubmit={handleSubmit} className="mt-5 flex flex-col gap-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label="Senha atual" error={errors.current_password} required>
            <PasswordInput
              name="current_password"
              value={values.current_password}
              onChange={handleChange}
              autoComplete="current-password"
              maxLength={128}
            />
          </FormField>
          <FormField
            label="Nova senha"
            error={errors.new_password}
            hint="8 a 128 caracteres, com letra maiúscula, número e caractere especial."
            required
          >
            <PasswordInput
              name="new_password"
              value={values.new_password}
              onChange={handleChange}
              autoComplete="new-password"
              maxLength={128}
            />
          </FormField>
        </div>
        <div className="flex justify-end">
          <button type="submit" disabled={mutation.isPending} className={submitClassName}>
            {mutation.isPending ? 'Salvando…' : 'Trocar senha'}
          </button>
        </div>
      </form>
    </SettingsCard>
  );
}
