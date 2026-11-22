import { isoToBrDate, parseBrDate } from './format';

const DAY_MS = 24 * 60 * 60 * 1000;

/** Duração inclusiva (RN-36): de 01/12 a 03/12 são 3 dias; início igual ao fim é 1 dia. */
export function rentalDays(startIso, endIso) {
  const start = Date.parse(`${startIso}T00:00:00Z`);
  const end = Date.parse(`${endIso}T00:00:00Z`);
  return Math.round((end - start) / DAY_MS) + 1;
}

/** Valor estimado (RN-43): valor por dia × duração, em reais. Informativo, sem cobrança. */
export function estimatedTotal(dailyPrice, days) {
  return (Number(dailyPrice) * days).toFixed(2);
}

/**
 * Valida o período digitado (dd/mm/aaaa) com as regras que a tela também confere
 * (RN-37, RN-38, RN-39). A API continua decidindo; aqui é só um auxílio.
 */
export function validateProposal({ start, end }, listing, today) {
  const errors = {};
  const values = { start_date: parseBrDate(start), end_date: parseBrDate(end) };

  if (!start.trim()) errors.start_date = 'Informe a data de início.';
  else if (!values.start_date) errors.start_date = 'Data inválida. Use dd/mm/aaaa.';
  else if (values.start_date < today) errors.start_date = 'O início não pode ser antes de hoje.';

  if (!end.trim()) errors.end_date = 'Informe a data de fim.';
  else if (!values.end_date) errors.end_date = 'Data inválida. Use dd/mm/aaaa.';
  else if (values.start_date && values.end_date < values.start_date) {
    errors.end_date = 'O fim deve ser no mesmo dia ou depois do início.';
  }

  const datesOk = !errors.start_date && !errors.end_date;
  if (datesOk) {
    const from = listing.available_from;
    const until = listing.available_until;
    if ((from && values.start_date < from) || (until && values.end_date > until)) {
      errors.end_date = `Escolha datas entre ${isoToBrDate(from)} e ${isoToBrDate(until)}.`;
    } else if (rentalDays(values.start_date, values.end_date) > listing.max_days) {
      errors.end_date =
        listing.max_days === 1
          ? 'Este item é alugado por no máximo 1 dia.'
          : `Este item é alugado por no máximo ${listing.max_days} dias.`;
    }
  }

  return { values, errors };
}

/** Resumo "N dia(s) · R$ X" (F-33) quando as duas datas formam um período válido. */
export function proposalSummary({ start, end }, dailyPrice) {
  const startIso = parseBrDate(start);
  const endIso = parseBrDate(end);
  if (!startIso || !endIso || endIso < startIso) return null;
  const days = rentalDays(startIso, endIso);
  return { days, total: estimatedTotal(dailyPrice, days) };
}

/** Valor por dia do aluguel: o congelado na proposta ou, na falta dele, total ÷ dias. */
function dailyPriceOf(rental) {
  if (rental.daily_price_snapshot) return Number(rental.daily_price_snapshot);
  return Number(rental.estimated_total) / rentalDays(rental.start_date, rental.end_date);
}

/**
 * Devolução antecipada (RN-50, seção 4.1): se o item volta hoje, antes do fim, o período
 * termina hoje e o valor informativo passa a contar só os dias usados. Devolve null quando
 * não é antecipada (hoje já é o último dia ou depois).
 */
export function earlyReturnSummary(rental, today) {
  if (today >= rental.end_date || today < rental.start_date) return null;
  const days = rentalDays(rental.start_date, today);
  return {
    days,
    total: estimatedTotal(dailyPriceOf(rental), days),
    originalDays: rentalDays(rental.start_date, rental.end_date),
    originalTotal: Number(rental.estimated_total).toFixed(2),
  };
}
