import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { cancelRental } from '../services/rentals';
import ConfirmDialog from './ConfirmDialog';

const NOT_ALLOWED_MESSAGE =
  'Não é mais possível cancelar: o aluguel já começou. Combine a devolução com o dono.';

/**
 * Cancelar (F-36): o locatário cancela a proposta, ou o aluguel aceito até a véspera do
 * início. O dono nunca cancela aluguel aceito (RN-51), por isso o botão não aparece para ele.
 */
export default function CancelRentalButton({ rental }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState('');
  const isProposal = rental.status === 'pending';

  const mutation = useMutation({
    mutationFn: () => cancelRental(rental.id),
    onSuccess: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ['rentals'] });
    },
    onError: (error) => {
      setOpen(false);
      setProblem(error.code === 'CANCEL_NOT_ALLOWED' ? NOT_ALLOWED_MESSAGE : error.message);
    },
  });

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          setProblem('');
          setOpen(true);
        }}
        className="rounded-lg border border-flow/40 px-3 py-1.5 text-sm font-medium text-flow hover:bg-flow/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow"
      >
        {isProposal ? 'Cancelar proposta' : 'Cancelar aluguel'}
      </button>
      {problem && (
        <p role="alert" className="mt-2 text-sm text-red-300">
          {problem}
        </p>
      )}
      <ConfirmDialog
        open={open}
        title={isProposal ? 'Cancelar proposta?' : 'Cancelar aluguel?'}
        description={
          isProposal
            ? 'O dono deixa de ver esta proposta.'
            : 'O dono é avisado e o período volta a ficar livre para outras pessoas.'
        }
        confirmLabel={mutation.isPending ? 'Cancelando…' : 'Sim, cancelar'}
        cancelLabel="Voltar"
        destructive
        busy={mutation.isPending}
        onConfirm={() => mutation.mutate()}
        onCancel={() => setOpen(false)}
      />
    </div>
  );
}
