import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from '../hooks/useAuth';
import LoadingScreen from './LoadingScreen';

/**
 * Rota privada sem sessão leva a /login, guardando o destino (seção 11.1). Quem saiu
 * pelo botão Sair vai ao login sem destino guardado.
 */
export default function PrivateRoute() {
  const { isAuthenticated, isLoading, loggedOut } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={loggedOut ? undefined : { from: location }} />;
  }
  return <Outlet />;
}
