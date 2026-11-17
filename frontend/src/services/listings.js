import { api } from './api';

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
