import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { proposeRental } from '../services/rentals';
import { todayIso } from '../utils/format';
import { validateProposal } from '../utils/rentalPeriod';
import DateRangePicker from './DateRangePicker';

const EMPTY = { start: '', end: '' };

const primaryClassName =
  'rounded-lg bg-accent px-6 py-3 font-semibold text-ink shadow-lg shadow-accent/10 ' +
  'transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 ' +
  'focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas ' +
  'disabled:opacity-60';

/** Mensagens claras para as recusas da API (seção 10). */
function problemFrom(error) {
  switch (error.code) {
    case 'RENTAL_OVERLAP':
      return {
        text: 'Esse período já está reservado para outro aluguel. Veja os períodos reservados e escolha outras datas.',
      };
    case 'DUPLICATE_PROPOSAL':
      return {
        text: 'Você já tem uma proposta pendente para este item com datas que se sobrepõem. Aguarde a resposta do dono ou cancele a anterior.',
        rentals: true,
      };
    case 'LISTING_UNAVAILABLE':
      return { text: 'Este anúncio não está mais disponível para propostas.' };
    default:
      if (error.status === 403) return { text: 'Você não pode alugar o próprio item.' };
      return { text: error.message };
  }
}

/**
 * Propor aluguel (F-30, F-32 a F-34): o botão abre a escolha do período; a tela confere
 * as regras básicas (RN-37 a RN-39) e a API decide. Não aparece para o dono (RN-33).
 */
export default function ProposalPanel({ listing }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [period, setPeriod] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [problem, setProblem] = useState(null);
  const [sent, setSent] = useState(false);
  const panelRef = useRef(null);
  const id = String(listing.id);

  useEffect(() => {
    if (open) panelRef.current?.querySelector('input')?.focus();
  }, [open]);

  const mutation = useMutation({
    mutationFn: (values) => proposeRental(id, values),
    onSuccess: () => {
      setSent(true);
      setOpen(false);
      setPeriod(EMPTY);
      queryClient.invalidateQueries({ queryKey: ['rentals'] });
    },
    onError: (error) => {
      if (error.status === 422 && Object.keys(error.fields).length > 0) {
        setErrors(error.fields);
        setProblem({ text: error.message });
        return;
      }
      setProblem(problemFrom(error));
      if (error.code === 'RENTAL_OVERLAP') {
        queryClient.invalidateQueries({ queryKey: ['listing', id, 'booked-periods'] });
      }
      if (error.code === 'LISTING_UNAVAILABLE') {
        queryClient.invalidateQueries({ queryKey: ['listing', id] });
      }
    },
  });

  function handleChange(next) {
    setPeriod(next);
    setErrors({});
    setProblem(null);
  }

  function handleSubmit(event) {
    event.preventDefault();
    const result = validateProposal(period, listing, todayIso());
    setErrors(result.errors);
    setProblem(null);
    if (Object.keys(result.errors).length === 0) mutation.mutate(result.values);
  }

  if (!open) {
    return (
      <div className="flex flex-col gap-3">
        {sent && (
          <p
            role="status"
            className="rounded-lg border border-flow/30 bg-flow/10 px-4 py-3 text-sm text-teal-100"
          >
            Proposta enviada! O dono tem 48 horas para responder.{' '}
            <Link to="/alugueis" className="font-medium text-white underline">
              Ver meus aluguéis
            </Link>
          </p>
        )}
        <button
          type="button"
          onClick={() => {
            setSent(false);
            setOpen(true);
          }}
          className={primaryClassName}
        >
          Propor aluguel
        </button>
      </div>
    );
  }

  return (
    <section
      ref={panelRef}
      aria-labelledby="propor-aluguel"
      className="rounded-xl border border-accent/40 bg-panel p-5"
    >
      <h2 id="propor-aluguel" className="font-semibold text-white">
        Propor aluguel
      </h2>
      <p className="mt-1 text-sm text-slate-400">
        {listing.max_days === 1 ? 'Até 1 dia' : `Até ${listing.max_days} dias`}, dentro da janela do
        anúncio. O dono tem 48 horas para responder.
      </p>
      <form noValidate onSubmit={handleSubmit} className="mt-5">
        <DateRangePicker
          value={period}
          errors={errors}
          dailyPrice={listing.daily_price}
          onChange={handleChange}
        />
        {problem && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-200"
          >
            {problem.text}{' '}
            {problem.rentals && (
              <Link to="/alugueis" className="font-medium text-red-100 underline">
                Ver meus aluguéis
              </Link>
            )}
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              setErrors({});
              setProblem(null);
            }}
            disabled={mutation.isPending}
            className="rounded-lg border border-flow/40 px-4 py-3 font-medium text-flow hover:bg-flow/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow disabled:opacity-60"
          >
            Cancelar
          </button>
          <button type="submit" disabled={mutation.isPending} className={primaryClassName}>
            {mutation.isPending ? 'Enviando…' : 'Enviar proposta'}
          </button>
        </div>
      </form>
    </section>
  );
}
