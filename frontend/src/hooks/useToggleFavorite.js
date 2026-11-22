import { useMutation, useQueryClient } from '@tanstack/react-query';
import { setFavorite } from '../services/listings';

/** Troca o is_favorite de um anúncio em todas as páginas do feed já carregadas. */
function markFavorite(data, id, favorite) {
  if (!data?.pages) return data;
  return {
    ...data,
    pages: data.pages.map((page) => ({
      ...page,
      items: page.items.map((item) => (item.id === id ? { ...item, is_favorite: favorite } : item)),
    })),
  };
}

/**
 * Coração do card (F-26), com ação otimista (seção 11.2): o card muda na hora; se a API
 * recusar, volta ao que era. No fim, as chaves ['listings', ...] são invalidadas, e o
 * filtro "Favoritos" passa a refletir a mudança.
 */
export function useToggleFavorite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, favorite }) => setFavorite(id, favorite),
    onMutate: async ({ id, favorite }) => {
      await queryClient.cancelQueries({ queryKey: ['listings'] });
      const previous = queryClient.getQueriesData({ queryKey: ['listings'] });
      queryClient.setQueriesData({ queryKey: ['listings'] }, (data) =>
        markFavorite(data, id, favorite),
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      for (const [key, data] of context?.previous ?? []) queryClient.setQueryData(key, data);
    },
    onSettled: (_data, _error, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['listing', String(id)] });
    },
  });
}
