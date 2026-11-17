import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from '../hooks/useAuth';
import LoadingScreen from './LoadingScreen';

/**
 * /login e /cadastro: quem já está logado é redirecionado a / (seção 11.1), ou à rota
 * privada que tentou abrir antes do login.
 */
export default function PublicOnlyRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen />;
  if (isAuthenticated) {
    const from = location.state?.from;
    const destination = from ? `${from.pathname}${from.search ?? ''}${from.hash ?? ''}` : '/';
    return <Navigate to={destination} replace />;
  }
  return <Outlet />;
}
