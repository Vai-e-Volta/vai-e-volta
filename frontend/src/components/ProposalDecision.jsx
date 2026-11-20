import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { acceptRental, rejectRental } from '../services/rentals';
import ConfirmDialog from './ConfirmDialog';

const DIALOGS = {
  accept: {
    title: 'Aceitar proposta?',
    description:
      'O aluguel fica reservado nessas datas. Outras propostas pendentes que se sobrepõem são recusadas automaticamente, e vocês passam a ver o telefone um do outro.',
    confirmLabel: 'Aceitar proposta',
    destructive: false,
  },
  reject: {
    title: 'Recusar proposta?',
    description: 'O locatário é avisado. Não é preciso informar o motivo.',
    confirmLabel: 'Recusar proposta',
    destructive: true,
  },
};

const ACTIONS = { accept: acceptRental, reject: rejectRental };

/** Recusas da API para aceitar ou recusar (seção 10). */
function messageFrom(error) {
  switch (error.code) {
    case 'RENTAL_OVERLAP':
      return 'Outro aluguel já foi aceito para essas datas, então esta proposta não pode mais ser aceita.';
    case 'PROPOSAL_EXPIRED':
      return 'Esta proposta expirou: passaram 48 horas ou a data de início já chegou.';
    case 'INVALID_STATE':
      return 'Esta proposta já foi respondida ou cancelada. A lista foi atualizada.';
    default:
      return error.message;
  }
}

/**
 * Aceitar e recusar proposta recebida (F-39, F-44), com confirmação. Depois de qualquer
 * resposta, inclusive erro, a lista recarrega para mostrar a situação atual.
 */
export default function ProposalDecision({ rental }) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState(null);
  const [problem, setProblem] = useState('');

  const mutation = useMutation({
    mutationFn: (action) => ACTIONS[action](rental.id),
    onError: (error) => setProblem(messageFrom(error)),
    onSettled: () => {
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ['rentals'] });
      queryClient.invalidateQueries({ queryKey: ['listing', String(rental.listing?.id)] });
      queryClient.invalidateQueries({ queryKey: ['me', 'listings'] });
    },
  });

  const config = dialog ? DIALOGS[dialog] : null;
  const busy = mutation.isPending;

  function open(action) {
    setProblem('');
    setDialog(action);
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => open('accept')}
          disabled={busy}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-ink hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:opacity-60"
        >
          Aceitar
        </button>
        <button
          type="button"
          onClick={() => open('reject')}
          disabled={busy}
          className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-slate-200 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60"
        >
          Recusar
        </button>
      </div>
      {problem && (
        <p role="alert" className="mt-2 text-sm text-red-300">
          {problem}
        </p>
      )}
      <ConfirmDialog
        open={Boolean(config)}
        title={config?.title}
        description={config?.description}
        confirmLabel={busy ? 'Aguarde…' : config?.confirmLabel}
        cancelLabel="Voltar"
        destructive={config?.destructive}
        busy={busy}
        onConfirm={() => mutation.mutate(dialog)}
        onCancel={() => setDialog(null)}
      />
    </div>
  );
}
