import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import { useAuth } from '../hooks/useAuth';
import { deleteAccount } from '../services/me';
import ConfirmDialog from './ConfirmDialog';
import FormField from './FormField';
import PasswordInput from './PasswordInput';
import { SettingsCard } from './SettingsCard';

const ACTIVE_RENTAL_MESSAGE =
  'Você tem um aluguel aceito em andamento ou agendado, como locatário ou como dono. ' +
  'Conclua ou cancele esses aluguéis antes de excluir a conta.';

/**
 * Excluir conta (F-13): confirmação com a senha (RN-16). Não é possível excluir com
 * aluguel aceito em curso ou futuro (RN-18, 409). Depois do 204, vai ao login.
 */
export default function DeleteAccountSection() {
  const { endSession } = useAuth();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [blocked, setBlocked] = useState('');

  const mutation = useMutation({
    mutationFn: deleteAccount,
    // A API já apagou o cookie: encerra a sessão local e a rota privada leva ao login.
    onSuccess: () => endSession('account_deleted'),
    onError: (error) => {
      if (error.status === 401) {
        setPassword('');
        setPasswordError('Senha incorreta.');
        document.getElementById('delete-account-password')?.focus();
        return;
      }
      setOpen(false);
      setPassword('');
      setBlocked(
        error.code === 'ACCOUNT_HAS_ACTIVE_RENTAL' ? ACTIVE_RENTAL_MESSAGE : error.message,
      );
    },
  });

  function openDialog() {
    setBlocked('');
    setPassword('');
    setPasswordError('');
    setOpen(true);
  }

  function handleConfirm() {
    if (!password) {
      setPasswordError('Informe sua senha para confirmar.');
      document.getElementById('delete-account-password')?.focus();
      return;
    }
    mutation.mutate(password);
  }

  return (
    <SettingsCard tone="danger" title="Excluir conta">
      <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-300">
        <li>Seus anúncios ficam pausados e deixam de aparecer no feed.</li>
        <li>Propostas pendentes, enviadas ou recebidas, são canceladas.</li>
        <li>
          Seus dados ficam guardados por 1 ano. Se entrar de novo nesse prazo, a conta volta e os
          anúncios voltam pausados. Depois disso, os dados pessoais são apagados.
        </li>
        <li>Com aluguel aceito em andamento ou agendado, não é possível excluir a conta.</li>
      </ul>

      {blocked && (
        <div
          role="alert"
          className="mt-5 rounded-lg border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-200"
        >
          {blocked}{' '}
          {blocked === ACTIVE_RENTAL_MESSAGE && (
            <Link
              to="/alugueis"
              className="font-semibold text-red-100 underline underline-offset-2 hover:text-white"
            >
              Ver meus aluguéis
            </Link>
          )}
        </div>
      )}

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          onClick={openDialog}
          className="rounded-lg border border-red-400/50 px-5 py-2.5 font-semibold text-red-200 transition-colors hover:bg-red-400/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
        >
          Excluir conta
        </button>
      </div>

      <ConfirmDialog
        open={open}
        title="Excluir sua conta?"
        description="Seus anúncios serão pausados e as propostas pendentes, canceladas. Você pode voltar entrando de novo em até 1 ano."
        confirmLabel={mutation.isPending ? 'Excluindo…' : 'Excluir conta'}
        destructive
        busy={mutation.isPending}
        onConfirm={handleConfirm}
        onCancel={() => setOpen(false)}
      >
        <FormField label="Sua senha" error={passwordError} required>
          <PasswordInput
            id="delete-account-password"
            name="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              setPasswordError('');
            }}
            autoComplete="current-password"
            maxLength={128}
          />
        </FormField>
      </ConfirmDialog>
    </SettingsCard>
  );
}
