import { useInfiniteQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import CancelRentalButton from '../components/CancelRentalButton';
import CompleteRentalButton from '../components/CompleteRentalButton';
import OwnerListingActions from '../components/OwnerListingActions';
import ProposalDecision from '../components/ProposalDecision';
import RentalCard from '../components/RentalCard';
import { uploadUrl } from '../services/listings';
import { getMyListings, getMyRentals } from '../services/rentals';
import { formatCurrency, todayIso } from '../utils/format';

// Visão e aba ficam na URL para que os avisos (RN-67) e o botão voltar levem ao lugar certo.
const VIEWS = [
  { value: 'anuncios', label: 'Meus anúncios' },
  { value: 'alugando', label: 'Itens que estou alugando' },
];
const SCOPES = [
  { value: 'ativos', scope: 'active', label: 'Ativos' },
  { value: 'historico', scope: 'history', label: 'Histórico' },
];

const LISTING_STATUS = { active: 'Ativo', paused: 'Pausado', deleted: 'Excluído' };
const LISTING_SITUATION = { available: 'Disponível', rented: 'Alugado' };

function pick(options, value) {
  return options.some((option) => option.value === value) ? value : options[0].value;
}

/**
 * O locatário cancela a proposta, ou o aluguel aceito até a véspera do início (F-36).
 * O dono nunca vê o botão em aluguel aceito (RN-51).
 */
function canCancel(rental, today) {
  if (rental.status === 'pending') return true;
  return rental.status === 'accepted' && rental.start_date > today;
}

/** O dono marca como devolvido o aluguel aceito que já começou (F-40, RN-64). */
function canComplete(rental, today) {
  return rental.status === 'accepted' && rental.start_date <= today;
}

function usePagedQuery(queryKey, fetchPage) {
  return useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) => fetchPage(pageParam),
    initialPageParam: null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}

function PagedList({ query, emptyText, children }) {
  if (query.isPending) return <p className="text-slate-400">Carregando…</p>;
  if (query.isError && !query.data) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-200"
      >
        Não foi possível carregar. {query.error.message}{' '}
        <button
          type="button"
          onClick={() => query.refetch()}
          className="font-medium text-red-100 underline"
        >
          Tentar de novo
        </button>
      </div>
    );
  }
  const items = query.data.pages.flatMap((page) => page.items);
  if (items.length === 0) return <p className="text-slate-400">{emptyText}</p>;
  return (
    <>
      <ul className="flex flex-col gap-3">
        {items.map((item) => (
          <li key={item.id}>{children(item)}</li>
        ))}
      </ul>
      {query.hasNextPage && (
        <button
          type="button"
          onClick={() => query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
          className="mt-4 rounded-lg border border-line px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60"
        >
          {query.isFetchingNextPage ? 'Carregando…' : 'Carregar mais'}
        </button>
      )}
    </>
  );
}

function MyListingRow({ listing }) {
  const cover = uploadUrl(listing.cover_photo);
  const status = LISTING_STATUS[listing.status] ?? listing.status;
  const situation = LISTING_SITUATION[listing.situation];
  return (
    <article
      aria-label={listing.title}
      className="flex gap-4 rounded-xl border border-line bg-panel p-4"
    >
      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-surface sm:h-20 sm:w-28">
        {cover && <img src={cover} alt="" className="h-full w-full object-cover" />}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="font-medium text-white">
          {listing.status === 'deleted' ? (
            listing.title
          ) : (
            <Link
              to={`/itens/${listing.id}`}
              className="rounded hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              {listing.title}
            </Link>
          )}
        </h3>
        <p className="mt-1 text-sm text-slate-400">
          {[status, situation].filter(Boolean).join(' · ')} ·{' '}
          <span className="text-accent">{formatCurrency(listing.daily_price)}</span> por dia
        </p>
        {listing.status !== 'deleted' && (
          <div className="mt-3">
            <OwnerListingActions listing={listing} />
          </div>
        )}
      </div>
    </article>
  );
}

function OwnerView({ scope }) {
  const rentals = usePagedQuery(['rentals', 'owner', scope], (cursor) =>
    getMyRentals({ role: 'owner', scope }, cursor),
  );
  const listings = usePagedQuery(['me', 'listings', scope], (cursor) =>
    getMyListings({ scope }, cursor),
  );
  const history = scope === 'history';
  const today = todayIso();
  return (
    <div className="flex flex-col gap-8">
      <section aria-labelledby="propostas-recebidas">
        <h2 id="propostas-recebidas" className="mb-3 font-semibold text-white">
          {history ? 'Aluguéis encerrados' : 'Propostas e aluguéis'}
        </h2>
        <PagedList
          query={rentals}
          emptyText={
            history
              ? 'Nenhum aluguel encerrado ainda.'
              : 'Nenhuma proposta ou aluguel em andamento nos seus anúncios.'
          }
        >
          {(rental) => (
            <RentalCard rental={rental} role="owner">
              {rental.status === 'pending' && rental.situation === 'Aguardando' && (
                <ProposalDecision rental={rental} />
              )}
              {canComplete(rental, today) && <CompleteRentalButton rental={rental} />}
            </RentalCard>
          )}
        </PagedList>
      </section>
      <section aria-labelledby="meus-anuncios">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="meus-anuncios" className="font-semibold text-white">
            {history ? 'Anúncios encerrados' : 'Anúncios'}
          </h2>
          {!history && (
            <Link
              to="/anunciar"
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ink hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
            >
              Anunciar item
            </Link>
          )}
        </div>
        <PagedList
          query={listings}
          emptyText={history ? 'Nenhum anúncio encerrado.' : 'Você ainda não anunciou nenhum item.'}
        >
          {(listing) => <MyListingRow listing={listing} />}
        </PagedList>
      </section>
    </div>
  );
}

function RenterView({ scope }) {
  const rentals = usePagedQuery(['rentals', 'renter', scope], (cursor) =>
    getMyRentals({ role: 'renter', scope }, cursor),
  );
  const today = todayIso();
  return (
    <section aria-labelledby="alugando">
      <h2 id="alugando" className="sr-only">
        Itens que estou alugando
      </h2>
      <PagedList
        query={rentals}
        emptyText={
          scope === 'history'
            ? 'Nenhum aluguel encerrado ainda.'
            : 'Você não está alugando nada agora. Encontre um item no feed.'
        }
      >
        {(rental) => (
          <RentalCard rental={rental} role="renter">
            {canCancel(rental, today) && <CancelRentalButton rental={rental} />}
          </RentalCard>
        )}
      </PagedList>
    </section>
  );
}

function Tabs({ label, options, value, onChange, variant }) {
  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const selected = option.value === value;
        const base =
          variant === 'pill'
            ? 'rounded-full px-4 py-2 text-sm font-medium'
            : 'border-b-2 px-1 pb-2 text-sm font-medium';
        const state =
          variant === 'pill'
            ? selected
              ? 'bg-accent text-ink'
              : 'border border-line text-slate-300 hover:bg-white/5'
            : selected
              ? 'border-accent text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200';
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.value)}
            className={`${base} ${state} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Tela Aluguéis (F-42 a F-45): alterna "Meus anúncios" e "Itens que estou alugando",
 * cada uma com ativos e histórico (RN-66), e mostra a situação de cada aluguel (RN-65).
 * Em "Meus anúncios", o dono aceita ou recusa as propostas recebidas (F-39, F-44).
 */
export default function RentalsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = pick(VIEWS, searchParams.get('visao'));
  const tab = pick(SCOPES, searchParams.get('aba'));
  const { scope } = SCOPES.find((option) => option.value === tab);

  function change(key, value) {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    setSearchParams(next, { replace: true });
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Aluguéis</h1>
      <div className="mt-6 flex flex-col gap-5">
        <Tabs
          label="Visão"
          options={VIEWS}
          value={view}
          onChange={(v) => change('visao', v)}
          variant="pill"
        />
        <div className="border-b border-line">
          <Tabs label="Período" options={SCOPES} value={tab} onChange={(v) => change('aba', v)} />
        </div>
      </div>
      <div role="tabpanel" className="mt-6">
        {view === 'anuncios' ? <OwnerView scope={scope} /> : <RenterView scope={scope} />}
      </div>
    </div>
  );
}
