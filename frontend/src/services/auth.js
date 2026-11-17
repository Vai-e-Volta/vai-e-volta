import { api } from './api';

/** Cadastro (F-01): POST /api/auth/register. */
export function registerUser(payload) {
  return api.post('/auth/register', payload);
}
