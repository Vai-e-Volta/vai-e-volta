import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { requestReturn } from '../services/rentals';
import { formatCurrency } from '../utils/format';
import { earlyReturnSummary } from '../utils/rentalPeriod';
import ConfirmDialog from './ConfirmDialog';

const days = (n) => (n === 1 ? '1 dia' : `${n} dias`);

/**
 * Devolver antes do prazo (F-37, RN-50): o locatário avisa; o dono confirma quando
 * receber o item, e só então o período encurta e o valor é recalculado.
 */
export default function ReturnRequestButton({ rental, today }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState('');
  const summary = earlyReturnSummary(rental, today);

  const mutation = useMutation({
    mutationFn: () => requestReturn(rental.id),
    onError: (error) => setProblem(error.message),
    onSettled: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ['rentals'] });
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
        Devolver antes do prazo
      </button>
      {problem && (
        <p role="alert" className="mt-2 text-sm text-red-300">
          {problem}
        </p>
      )}
      <ConfirmDialog
        open={open}
        title="Devolver antes do prazo?"
        description="O dono é avisado e confirma a devolução quando receber o item. O período restante fica livre para outras pessoas."
        confirmLabel={mutation.isPending ? 'Aguarde…' : 'Avisar o dono'}
        cancelLabel="Voltar"
        busy={mutation.isPending}
        onConfirm={() => mutation.mutate()}
        onCancel={() => setOpen(false)}
      >
        {summary && (
          <p className="text-sm text-slate-300">
            Devolvendo hoje, o valor estimado passa de {days(summary.originalDays)} ·{' '}
            {formatCurrency(summary.originalTotal)} para{' '}
            <span className="font-semibold text-white">
              {days(summary.days)} · {formatCurrency(summary.total)}
            </span>
            .
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}
