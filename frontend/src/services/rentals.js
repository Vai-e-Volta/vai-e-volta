import { api } from './api';

/**
 * Propor aluguel (F-34): POST /api/listings/{id}/rentals com { start_date, end_date }
 * (AAAA-MM-DD). A proposta nasce pendente e só vale depois do aceite (RN-41).
 */
export function proposeRental(listingId, period) {
  return api.post(`/listings/${encodeURIComponent(listingId)}/rentals`, period);
}

function pageQuery(params, cursor) {
  const query = new URLSearchParams(params);
  query.set('limit', '20');
  if (cursor) query.set('cursor', cursor);
  return query.toString();
}

/** Aceita a página { items, next_cursor } ou uma lista simples. */
function asPage(data) {
  if (Array.isArray(data)) return { items: data, next_cursor: null };
  return { items: data?.items ?? [], next_cursor: data?.next_cursor ?? null };
}

/**
 * Aluguéis da pessoa (F-42, F-43): role=renter são os itens que ela está alugando;
 * role=owner, as propostas e os aluguéis dos anúncios dela. scope=active|history (RN-66).
 */
export async function getMyRentals({ role, scope }, cursor = null) {
  return asPage(await api.get(`/me/rentals?${pageQuery({ role, scope }, cursor)}`));
}

/** Meus anúncios (F-41, F-43): GET /api/me/listings?scope=active|history. */
export async function getMyListings({ scope }, cursor = null) {
  return asPage(await api.get(`/me/listings?${pageQuery({ scope }, cursor)}`));
}

/** Cancelar proposta ou aluguel (F-36): só o locatário, até a véspera do início. */
export function cancelRental(id) {
  return api.post(`/rentals/${encodeURIComponent(id)}/cancel`);
}

/** Aceitar proposta (F-39): só o dono. Recusa as pendentes sobrepostas (RN-46). */
export function acceptRental(id) {
  return api.post(`/rentals/${encodeURIComponent(id)}/accept`);
}

/** Recusar proposta (F-39): só o dono, sem motivo (RN-63). */
export function rejectRental(id) {
  return api.post(`/rentals/${encodeURIComponent(id)}/reject`);
}

/** Marcar como devolvido (F-40): só o dono, com o aluguel já iniciado (RN-64). */
export function completeRental(id) {
  return api.post(`/rentals/${encodeURIComponent(id)}/complete`);
}
