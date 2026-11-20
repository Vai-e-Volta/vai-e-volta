import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router';
import { applyFilterChanges, feedFiltersFromSearch } from '../utils/feedFilters';

/**
 * Filtros do feed guardados na URL (seção 11.2). `setFilters({ q: 'x' })` troca só as
 * chaves informadas; com `replace`, a mudança não cria uma entrada no histórico (usado
 * na busca, que muda enquanto a pessoa digita).
 */
export function useFeedFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => feedFiltersFromSearch(searchParams), [searchParams]);

  // O setSearchParams parte da URL da última renderização. Se duas mudanças chegam antes
  // de a tela atualizar (o fim da espera da busca e um clique numa categoria, por
  // exemplo), a segunda apagaria a primeira. Por isso as mudanças se acumulam aqui.
  const latest = useRef(searchParams);
  useEffect(() => {
    latest.current = searchParams;
  }, [searchParams]);

  const setFilters = useCallback(
    (changes, { replace = false } = {}) => {
      const next = applyFilterChanges(latest.current, changes);
      latest.current = next;
      setSearchParams(next, { replace });
    },
    [setSearchParams],
  );

  return { filters, setFilters };
}
