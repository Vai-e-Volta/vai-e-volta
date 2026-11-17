import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo } from 'react';
import { getCurrentUser, setUnauthorizedHandler } from '../services/api';
import { AuthContext } from './authContext';

const SESSION_QUERY_KEY = ['auth', 'me'];

async function fetchSession() {
  try {
    return await getCurrentUser();
  } catch {
    // Sem sessão (401) ou API indisponível: a pessoa é tratada como não logada.
    return null;
  }
}

/**
 * Sessão do usuário (Documento Técnico, seção 11.2). O cookie vv_session é HttpOnly,
 * então o usuário vem de GET /api/auth/me.
 */
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const { data: user = null, isPending } = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: fetchSession,
    staleTime: Infinity,
    retry: false,
  });

  const setUser = useCallback(
    (nextUser) => queryClient.setQueryData(SESSION_QUERY_KEY, nextUser),
    [queryClient],
  );

  const clearSession = useCallback(() => {
    queryClient.setQueryData(SESSION_QUERY_KEY, null);
  }, [queryClient]);

  // Em qualquer 401 a sessão é limpa; as rotas privadas levam então ao /login (RN-13).
  useEffect(() => setUnauthorizedHandler(clearSession), [clearSession]);

  const value = useMemo(
    () => ({ user, isAuthenticated: user !== null, isLoading: isPending, setUser, clearSession }),
    [user, isPending, setUser, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
