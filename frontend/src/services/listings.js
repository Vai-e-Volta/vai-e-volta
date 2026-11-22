import { toFeedQuery } from '../utils/feedFilters';
import { api } from './api';

/** Endereço de uma foto enviada, servida pelo Nginx em /uploads (seções 10 e 11.4). */
export function uploadUrl(filename) {
  return filename ? `/uploads/${encodeURIComponent(filename)}` : null;
}

/**
 * Feed (F-15, F-24): GET /api/listings com os filtros e o cursor da página.
 * Resposta { items, next_cursor, total } (RN-30).
 */
export function getFeed(filters, cursor = null) {
  return api.get(`/listings?${toFeedQuery(filters, cursor)}`);
}

/** Categorias fixas (RN-58): GET /api/categories. */
export async function getCategories() {
  const data = await api.get('/categories');
  return Array.isArray(data) ? data : (data?.categories ?? []);
}

/** Criar anúncio (F-38): POST /api/listings em multipart/form-data. */
export function createListing(formData) {
  return api.post('/listings', formData);
}

/** Anúncio (F-28, F-31): GET /api/listings/{id}. */
export function getListing(id) {
  return api.get(`/listings/${encodeURIComponent(id)}`);
}

/** Editar anúncio (F-41): PATCH /api/listings/{id} em multipart, só com o que mudou. */
export function updateListing(id, formData) {
  return api.patch(`/listings/${encodeURIComponent(id)}`, formData);
}
