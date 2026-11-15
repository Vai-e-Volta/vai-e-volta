import { api } from './api';

/** Editar dados (F-11): PATCH /api/me só com os campos alterados. */
export function updateMe(changes) {
  return api.patch('/me', changes);
}

/**
 * Trocar senha (F-12): PUT /api/me/password. Um 401 aqui é a senha atual incorreta,
 * não sessão expirada, então não leva ao login.
 */
export function changePassword({ currentPassword, newPassword }) {
  return api.put(
    '/me/password',
    { current_password: currentPassword, new_password: newPassword },
    { handleUnauthorized: false },
  );
}

/**
 * Excluir conta (F-13): DELETE /api/me com a senha atual (RN-16). A API apaga o cookie
 * e responde 204. Um 401 aqui é senha incorreta, não sessão expirada.
 */
export function deleteAccount(password) {
  return api.delete('/me', { password }, { handleUnauthorized: false });
}
