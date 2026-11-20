import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { completeRental } from '../services/rentals';
import { formatCurrency } from '../utils/format';
import { earlyReturnSummary } from '../utils/rentalPeriod';
import ConfirmDialog from './ConfirmDialog';

const days = (n) => (n === 1 ? '1 dia' : `${n} dias`);

function messageFrom(error) {
  if (error.code === 'INVALID_STATE') {
    return 'Só dá para marcar como devolvido um aluguel aceito que já começou. A lista foi atualizada.';
  }
  return error.message;
}

/**
 * Marcar como devolvido (F-40): o dono conclui o aluguel iniciado (RN-64). O aluguel vai
 * para o histórico dos dois; o atraso não gera multa. O botão é menta: o item voltou.
 * Se o locatário avisou a devolução antes do fim (RN-50), a confirmação mostra o valor
 * recalculado pelos dias usados.
 */
export default function CompleteRentalButton({ rental, today }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState('');
  const early = rental.return_requested_at ? earlyReturnSummary(rental, today) : null;

  const mutation = useMutation({
    mutationFn: () => completeRental(rental.id),
    onError: (error) => setProblem(messageFrom(error)),
    onSettled: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ['rentals'] });
      queryClient.invalidateQueries({ queryKey: ['listing', String(rental.listing?.id)] });
      queryClient.invalidateQueries({ queryKey: ['me', 'listings'] });
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
        className="rounded-lg bg-flow px-3 py-1.5 text-sm font-semibold text-ink hover:bg-flow-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
      >
        Marcar como devolvido
      </button>
      {problem && (
        <p role="alert" className="mt-2 text-sm text-red-300">
          {problem}
        </p>
      )}
      <ConfirmDialog
        open={open}
        title="Marcar como devolvido?"
        description="Confirme só depois de receber o item. O aluguel vai para o histórico e o locatário é avisado."
        confirmLabel={mutation.isPending ? 'Aguarde…' : 'Confirmar devolução'}
        cancelLabel="Voltar"
        busy={mutation.isPending}
        onConfirm={() => mutation.mutate()}
        onCancel={() => setOpen(false)}
      >
        {early && (
          <p className="text-sm text-slate-300">
            Devolução antes do prazo: o período termina hoje e o valor estimado passa de{' '}
            {days(early.originalDays)} · {formatCurrency(early.originalTotal)} para{' '}
            <span className="font-semibold text-white">
              {days(early.days)} · {formatCurrency(early.total)}
            </span>
            .
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}
