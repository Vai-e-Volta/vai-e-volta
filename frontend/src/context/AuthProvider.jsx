import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { getCurrentUser, setUnauthorizedHandler } from '../services/api';
import { logout as logoutRequest } from '../services/auth';
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
  // true quando a pessoa saiu pelo botão Sair: o login não guarda a rota de destino.
  const [loggedOut, setLoggedOut] = useState(false);
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

  // Sem sessão, os dados em cache da conta anterior são descartados.
  const clearSession = useCallback(() => {
    queryClient.removeQueries({
      predicate: (query) => query.queryKey[0] !== SESSION_QUERY_KEY[0],
    });
    queryClient.setQueryData(SESSION_QUERY_KEY, null);
  }, [queryClient]);

  // Depois do login o cookie já existe: busca o usuário de novo em /api/auth/me.
  const refreshSession = useCallback(() => {
    setLoggedOut(false);
    return queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
  }, [queryClient]);

  // Sair (F-08): a API apaga o cookie; a sessão local é limpa mesmo se a chamada falhar.
  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // Cookie já inválido (401) ou API fora do ar: a pessoa sai do mesmo jeito.
    } finally {
      setLoggedOut(true);
      clearSession();
    }
  }, [clearSession]);

  // Em qualquer 401 a sessão é limpa; as rotas privadas levam então ao /login (RN-13).
  useEffect(() => setUnauthorizedHandler(clearSession), [clearSession]);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading: isPending,
      setUser,
      clearSession,
      refreshSession,
      logout,
      loggedOut,
    }),
    [user, isPending, setUser, clearSession, refreshSession, logout, loggedOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
