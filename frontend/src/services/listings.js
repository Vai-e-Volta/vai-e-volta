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
