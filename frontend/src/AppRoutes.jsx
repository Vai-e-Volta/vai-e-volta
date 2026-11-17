import { Route, Routes } from 'react-router';
import AuthLayout from './components/AuthLayout';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import PublicOnlyRoute from './components/PublicOnlyRoute';
import EditListingPage from './pages/EditListingPage';
import FeedPage from './pages/FeedPage';
import ItemPage from './pages/ItemPage';
import LoginPage from './pages/LoginPage';
import NewListingPage from './pages/NewListingPage';
import NotFoundPage from './pages/NotFoundPage';
import NotificationsPage from './pages/NotificationsPage';
import RegisterPage from './pages/RegisterPage';
import RentalsPage from './pages/RentalsPage';
import SettingsPage from './pages/SettingsPage';
import UserProfilePage from './pages/UserProfilePage';

/** Mapa de rotas e acesso (Documento Técnico, seção 11.1). */
export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/cadastro" element={<RegisterPage />} />
        </Route>
      </Route>
      <Route element={<Layout />}>
        <Route element={<PrivateRoute />}>
          <Route path="/" element={<FeedPage />} />
          <Route path="/itens/:id" element={<ItemPage />} />
          <Route path="/anunciar" element={<NewListingPage />} />
          <Route path="/anuncios/:id/editar" element={<EditListingPage />} />
          <Route path="/alugueis" element={<RentalsPage />} />
          <Route path="/usuarios/:username" element={<UserProfilePage />} />
          <Route path="/configuracoes" element={<SettingsPage />} />
          <Route path="/notificacoes" element={<NotificationsPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
