import { api } from './api';

/**
 * Perfil público (F-10): GET /api/users/{username}. Traz só dados públicos (RN-15):
 * nome de usuário, bairro, cidade, data de cadastro e anúncios ativos.
 */
export function getPublicProfile(username) {
  return api.get(`/users/${encodeURIComponent(username)}`);
}
