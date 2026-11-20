import { api } from './api';

/**
 * Propor aluguel (F-34): POST /api/listings/{id}/rentals com { start_date, end_date }
 * (AAAA-MM-DD). A proposta nasce pendente e só vale depois do aceite (RN-41).
 */
export function proposeRental(listingId, period) {
  return api.post(`/listings/${encodeURIComponent(listingId)}/rentals`, period);
}
