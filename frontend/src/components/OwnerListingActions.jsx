import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import { deleteListing, pauseListing, resumeListing } from '../services/listings';
import ConfirmDialog from './ConfirmDialog';

const ACTIVE_RENTAL_MESSAGE =
  'Este anúncio tem um aluguel aceito em andamento ou agendado. Ele só pode ser pausado ou ' +
  'excluído depois que esse aluguel terminar.';

const DIALOGS = {
  pause: {
    title: 'Pausar anúncio?',
    description:
      'O anúncio sai do feed e as propostas pendentes são recusadas. Você pode reativar quando quiser.',
    confirmLabel: 'Pausar anúncio',
    destructive: false,
  },
  delete: {
    title: 'Excluir anúncio?',
    description:
      'O anúncio sai do feed e as propostas pendentes são recusadas. Não é possível desfazer.',
    confirmLabel: 'Excluir anúncio',
    destructive: true,
  },
};

const ACTIONS = { pause: pauseListing, resume: resumeListing, delete: deleteListing };

const secondaryClassName =
  'rounded-lg border border-line px-4 py-2.5 font-medium text-slate-200 hover:bg-white/5 ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60';

/**
 * Controles do anunciante (F-41): editar, pausar, reativar e excluir, com confirmação para
 * pausar e excluir. O 409 LISTING_HAS_ACTIVE_RENTAL (RN-62) vira uma explicação clara.
 * Usado na página do item e na lista "Meus anúncios".
 */
export default function OwnerListingActions({ listing, onDeleted }) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState(null);
  const [problem, setProblem] = useState(null);
  const id = String(listing.id);

  const mutation = useMutation({
    mutationFn: (action) => ACTIONS[action](id),
    onSuccess: (_data, action) => {
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ['listing', id] });
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['me', 'listings'] });
      if (action === 'delete') onDeleted?.();
    },
    onError: (error, action) => {
      setDialog(null);
      if (error.code === 'LISTING_HAS_ACTIVE_RENTAL')
        setProblem({ text: ACTIVE_RENTAL_MESSAGE, rentals: true });
      // Reativar com a janela já encerrada: a saída é editar as datas.
      else if (action === 'resume' && error.status === 409)
        setProblem({ text: error.message, edit: true });
      else setProblem({ text: error.message });
    },
  });

  function run(action) {
    setProblem(null);
    if (DIALOGS[action]) setDialog(action);
    else mutation.mutate(action);
  }

  const busy = mutation.isPending;
  const config = dialog ? DIALOGS[dialog] : null;

  return (
    <div>
      <div className="flex flex-wrap gap-3">
        <Link
          to={`/anuncios/${id}/editar`}
          className="rounded-lg bg-accent px-5 py-2.5 font-semibold text-ink hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        >
          Editar anúncio
        </Link>
        {listing.status === 'paused' ? (
          <button
            type="button"
            onClick={() => run('resume')}
            disabled={busy}
            className={secondaryClassName}
          >
            {busy && mutation.variables === 'resume' ? 'Reativando…' : 'Reativar'}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => run('pause')}
            disabled={busy}
            className={secondaryClassName}
          >
            Pausar
          </button>
        )}
        <button
          type="button"
          onClick={() => run('delete')}
          disabled={busy}
          className="rounded-lg border border-red-400/40 px-4 py-2.5 font-medium text-red-300 hover:bg-red-400/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:opacity-60"
        >
          Excluir
        </button>
      </div>

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
          {problem.edit && (
            <Link to={`/anuncios/${id}/editar`} className="font-medium text-red-100 underline">
              Editar as datas
            </Link>
          )}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(config)}
        title={config?.title}
        description={config?.description}
        confirmLabel={busy ? 'Aguarde…' : config?.confirmLabel}
        destructive={config?.destructive}
        busy={busy}
        onConfirm={() => mutation.mutate(dialog)}
        onCancel={() => setDialog(null)}
      />
    </div>
  );
}
