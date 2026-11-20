import { useId } from 'react';
import { Link } from 'react-router';
import { uploadUrl } from '../services/listings';
import { formatCurrency, formatRelativeTime } from '../utils/format';

// Situação calculada pela API (RN-65). Seguindo a regra do vai e volta, o item alugado
// "foi" (pêssego) e o disponível está de volta (menta).
const SITUATIONS = {
  available: { label: 'Disponível', dot: 'bg-flow' },
  rented: { label: 'Alugado', dot: 'bg-accent' },
};

function HeartIcon({ filled }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5">
      <path
        d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2Z"
        fill={filled ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Card do feed (F-23): foto, situação, categoria, nome, valor por dia, bairro e tempo
 * desde a publicação, com o selo "Seu anúncio" (RN-24) e o coração de favorito (F-26).
 * Só usa campos públicos (RN-15). O link cobre o card inteiro; o coração fica por cima.
 */
export default function ListingCard({ listing, now, onToggleFavorite }) {
  const titleId = useId();
  const situation = SITUATIONS[listing.situation];
  const cover = uploadUrl(listing.cover_photo);
  const canFavorite = Boolean(onToggleFavorite) && !listing.is_owner;

  return (
    <article
      aria-labelledby={titleId}
      className="group relative flex h-full flex-col overflow-hidden rounded-xl border border-line bg-panel transition-colors hover:border-accent has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-accent has-[a:focus-visible]:ring-offset-2 has-[a:focus-visible]:ring-offset-canvas"
    >
      <div className="relative aspect-[4/3] bg-surface">
        {cover ? (
          <img
            src={cover}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            Sem foto
          </div>
        )}
        <div className="absolute inset-x-2 top-2 flex flex-wrap items-start justify-between gap-1.5">
          {situation && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas/85 px-2.5 py-1 text-xs font-medium text-slate-100 backdrop-blur">
              <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${situation.dot}`} />
              {situation.label}
            </span>
          )}
          {listing.is_owner && (
            <span className="rounded-full bg-accent px-2.5 py-1 text-xs font-semibold text-ink">
              Seu anúncio
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {listing.category}
        </p>
        <h2 id={titleId} className="mt-1 line-clamp-2 font-medium text-white">
          <Link
            to={`/itens/${listing.id}`}
            className="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none"
          >
            {listing.title}
          </Link>
        </h2>
        <p className="mt-2 text-accent">
          <span className="font-semibold">{formatCurrency(listing.daily_price)}</span>{' '}
          <span className="text-sm text-slate-400">por dia</span>
        </p>
        <p className="mt-auto flex flex-wrap gap-x-1.5 pt-3 text-sm text-slate-400">
          <span>{listing.neighborhood}</span>
          <span aria-hidden="true">·</span>
          <time dateTime={listing.created_at}>{formatRelativeTime(listing.created_at, now)}</time>
        </p>
      </div>

      {canFavorite && (
        <button
          type="button"
          aria-pressed={listing.is_favorite}
          aria-label={`Favoritar ${listing.title}`}
          onClick={() => onToggleFavorite(listing)}
          className={`absolute right-2 top-2 z-10 flex h-9 w-9 items-center justify-center rounded-full bg-canvas/85 backdrop-blur transition-colors hover:bg-canvas focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
            listing.is_favorite ? 'text-accent' : 'text-slate-200 hover:text-accent'
          }`}
        >
          <HeartIcon filled={listing.is_favorite} />
        </button>
      )}
    </article>
  );
}
