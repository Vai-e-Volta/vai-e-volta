import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query';
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router';
import FilterSidebar from '../components/FilterSidebar';
import ListingCard from '../components/ListingCard';
import SearchField from '../components/SearchField';
import { useFeedFilters } from '../hooks/useFeedFilters';
import { getFeed } from '../services/listings';

const SKELETON_CARDS = 8;

const gridClassName = 'grid gap-4 sm:grid-cols-2 xl:grid-cols-3';

const retryButtonClassName =
  'rounded-lg border border-line px-4 py-2 font-medium text-slate-200 hover:bg-white/5 ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent';

function countLabel(total) {
  return total === 1 ? '1 item encontrado' : `${total.toLocaleString('pt-BR')} itens encontrados`;
}

function SkeletonGrid() {
  return (
    <ul aria-hidden="true" className={gridClassName}>
      {Array.from({ length: SKELETON_CARDS }, (_, index) => (
        <li key={index} className="overflow-hidden rounded-xl border border-line bg-panel">
          <div className="aspect-[4/3] animate-pulse bg-surface motion-reduce:animate-none" />
          <div className="space-y-2 p-4">
            <div className="h-3 w-1/3 rounded bg-surface" />
            <div className="h-4 w-3/4 rounded bg-surface" />
            <div className="h-4 w-1/2 rounded bg-surface" />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Quantos filtros da barra lateral estão em uso (a busca fica fora da conta). */
function countSidebarFilters(filters) {
  return Object.entries(filters)
    .filter(([key]) => key !== 'q')
    .reduce((count, [, value]) => count + (Array.isArray(value) ? value.length : 1), 0);
}

/**
 * Feed (F-15, F-23, F-24): grade de ListingCard com rolagem infinita por cursor
 * (RN-30), busca pelo nome (F-16) e barra lateral de filtros (F-25). Os filtros vêm da
 * URL, então a chave ['listings', filtros] muda junto com ela.
 */
export default function FeedPage() {
  const { filters, setFilters } = useFeedFilters();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const sidebarId = useId();
  const sentinelRef = useRef(null);
  const now = useMemo(() => new Date(), []);

  const {
    data,
    error,
    isPending,
    isError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    isPlaceholderData,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['listings', filters],
    queryFn: ({ pageParam }) => getFeed(filters, pageParam),
    initialPageParam: null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    // Ao trocar um filtro, a lista anterior continua na tela até a nova chegar.
    placeholderData: keepPreviousData,
  });

  const items = data?.pages.flatMap((page) => page.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;
  const nextPageFailed = isError && Boolean(data);
  const updating = isPlaceholderData;
  const activeFilters = countSidebarFilters(filters);

  // Carrega a próxima página quando o fim da lista se aproxima da tela.
  const canLoadMore = hasNextPage && !isFetchingNextPage && !nextPageFailed && !updating;
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !canLoadMore || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) fetchNextPage();
      },
      { rootMargin: '400px 0px' },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [canLoadMore, fetchNextPage]);

  return (
    <section>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            Itens para alugar
          </h1>
          <p aria-live="polite" className="mt-1 text-slate-400">
            {data ? countLabel(total) : ' '}
          </p>
        </div>
        <Link
          to="/anunciar"
          className="rounded-lg bg-accent px-5 py-2.5 font-semibold text-ink shadow-lg shadow-accent/10 transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        >
          Anunciar item
        </Link>
      </div>

      <div className="mt-6 flex gap-3">
        <div className="flex-1">
          <SearchField
            value={filters.q ?? ''}
            onSearch={(q) => setFilters({ q }, { replace: true })}
          />
        </div>
        <button
          type="button"
          aria-expanded={filtersOpen}
          aria-controls={sidebarId}
          onClick={() => setFiltersOpen((open) => !open)}
          className="rounded-lg border border-line px-4 font-medium text-slate-200 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent lg:hidden"
        >
          Filtros{activeFilters > 0 && ` (${activeFilters})`}
        </button>
      </div>

      <div className="mt-6 lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-8">
        <aside
          id={sidebarId}
          aria-label="Filtros"
          className={`${filtersOpen ? 'block' : 'hidden'} mb-6 rounded-xl border border-line bg-panel p-4 lg:mb-0 lg:block lg:self-start lg:border-0 lg:bg-transparent lg:p-0`}
        >
          <FilterSidebar filters={filters} onChange={(changes) => setFilters(changes)} />
        </aside>

        <div
          aria-busy={isPending || updating}
          className={`transition-opacity ${updating ? 'opacity-60' : ''}`}
        >
          {isPending && <SkeletonGrid />}

          {isError && !data && (
            <div
              role="alert"
              className="rounded-xl border border-line bg-panel px-6 py-10 text-center"
            >
              <p className="font-medium text-white">Não foi possível carregar os itens.</p>
              <p className="mt-1 text-sm text-slate-400">{error.message}</p>
              <button
                type="button"
                onClick={() => refetch()}
                className={`mt-5 ${retryButtonClassName}`}
              >
                Tentar de novo
              </button>
            </div>
          )}

          {data && items.length === 0 && (
            <p className="rounded-xl border border-line bg-panel px-6 py-10 text-center text-slate-400">
              Nenhum item encontrado.
            </p>
          )}

          {items.length > 0 && (
            <ul className={gridClassName}>
              {items.map((listing) => (
                <li key={listing.id}>
                  <ListingCard listing={listing} now={now} />
                </li>
              ))}
            </ul>
          )}

          {data && (
            <div ref={sentinelRef} className="mt-8 flex flex-col items-center gap-3">
              {isFetchingNextPage && (
                <p role="status" className="text-sm text-slate-400">
                  Carregando mais itens…
                </p>
              )}
              {nextPageFailed && (
                <p role="alert" className="text-sm text-red-300">
                  {error.message}
                </p>
              )}
              {hasNextPage && !isFetchingNextPage && (
                <button
                  type="button"
                  onClick={() => fetchNextPage()}
                  className={retryButtonClassName}
                >
                  {nextPageFailed ? 'Tentar de novo' : 'Carregar mais'}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
