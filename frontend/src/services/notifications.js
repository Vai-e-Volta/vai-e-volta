import { api } from './api';

/** Caixa de notificações (F-47): GET /api/notifications, paginada por cursor. */
export async function getNotifications(cursor = null) {
  const query = new URLSearchParams({ limit: '20' });
  if (cursor) query.set('cursor', cursor);
  const data = await api.get(`/notifications?${query}`);
  if (Array.isArray(data)) return { items: data, next_cursor: null };
  return { items: data?.items ?? [], next_cursor: data?.next_cursor ?? null };
}

/** Quantos avisos não lidos (F-46, RN-68). Aceita um número ou { count }. */
export async function getUnreadCount() {
  const data = await api.get('/notifications/unread-count');
  if (typeof data === 'number') return data;
  return Number(data?.count ?? data?.unread_count ?? 0);
}

/** Marcar um aviso como lido (F-52). */
export function markNotificationRead(id) {
  return api.post(`/notifications/${encodeURIComponent(id)}/read`);
}

/** Marcar todos como lidos (F-52). */
export function markAllNotificationsRead() {
  return api.post('/notifications/read-all');
}
