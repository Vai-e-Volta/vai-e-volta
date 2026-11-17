import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from '../hooks/useAuth';
import LoadingScreen from './LoadingScreen';

// Estado levado ao /login quando a própria pessoa encerrou a sessão.
const END_STATE = { logout: undefined, account_deleted: { accountDeleted: true } };

/**
 * Rota privada sem sessão leva a /login, guardando o destino (seção 11.1). Quem saiu
 * ou excluiu a conta vai ao login sem destino guardado.
 */
export default function PrivateRoute() {
  const { isAuthenticated, isLoading, sessionEnd } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen />;
  if (!isAuthenticated) {
    const state = sessionEnd ? END_STATE[sessionEnd] : { from: location };
    return <Navigate to="/login" replace state={state} />;
  }
  return <Outlet />;
}
