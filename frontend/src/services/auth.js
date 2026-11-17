import { api } from './api';

/** Cadastro (F-01): POST /api/auth/register. */
export function registerUser(payload) {
  return api.post('/auth/register', payload);
}

/**
 * Login (F-05): POST /api/auth/login com e-mail ou nome de usuário. A API define o
 * cookie de sessão; um 401 aqui é credencial incorreta, não sessão expirada.
 */
export function login({ identifier, password }) {
  return api.post('/auth/login', { identifier, password }, { handleUnauthorized: false });
}

/** Sair (F-08): POST /api/auth/logout. A API apaga o cookie de sessão. */
export function logout() {
  return api.post('/auth/logout', undefined, { handleUnauthorized: false });
}
