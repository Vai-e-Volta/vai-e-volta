import { Link } from 'react-router';
import { uploadUrl } from '../services/listings';
import { formatCurrency, isoToBrDate } from '../utils/format';
import { rentalDays } from '../utils/rentalPeriod';
import StatusBadge from './StatusBadge';

/** A outra parte do aluguel: o locatário para o dono e o dono para o locatário. */
function otherParty(rental, role) {
  return role === 'owner' ? rental.renter : rental.owner;
}

/**
 * Linha de aluguel ou proposta (F-42 a F-45): item, período, valor estimado, situação
 * (RN-65) e a outra parte. O telefone só vem da API depois do aceite (RN-17); conta
 * excluída aparece como "usuário excluído" (RN-19). As ações ficam em `children`.
 */
export default function RentalCard({ rental, role, children }) {
  const listing = rental.listing ?? {};
  const person = otherParty(rental, role);
  const cover = uploadUrl(listing.cover_photo);
  const days = rentalDays(rental.start_date, rental.end_date);

  return (
    <article
      aria-label={`${listing.title}, ${rental.situation}`}
      className="flex gap-4 rounded-xl border border-line bg-panel p-4"
    >
      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-surface sm:h-20 sm:w-28">
        {cover && <img src={cover} alt="" className="h-full w-full object-cover" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 className="font-medium text-white">
            <Link
              to={`/itens/${listing.id}`}
              className="rounded hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              {listing.title}
            </Link>
          </h3>
          <StatusBadge situation={rental.situation} />
        </div>
        <p className="mt-1 text-sm tabular-nums text-slate-300">
          {isoToBrDate(rental.start_date)} a {isoToBrDate(rental.end_date)} ·{' '}
          {days === 1 ? '1 dia' : `${days} dias`} ·{' '}
          <span className="text-accent">{formatCurrency(rental.estimated_total)}</span>
        </p>
        <p className="mt-1 text-sm text-slate-400">
          {role === 'owner' ? 'Locatário: ' : 'Dono: '}
          {person?.username ? (
            <Link
              to={`/usuarios/${encodeURIComponent(person.username)}`}
              className="rounded text-slate-200 hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              @{person.username}
            </Link>
          ) : (
            <span className="italic">usuário excluído</span>
          )}
          {person?.phone && <span className="text-slate-300"> · {person.phone}</span>}
        </p>
        {children && <div className="mt-3">{children}</div>}
      </div>
    </article>
  );
}
