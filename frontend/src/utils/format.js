// Formatos de exibição (seção 11.5 e RN-69): valores em R$ 0,00, datas em dd/mm/aaaa
// e fuso America/Sao_Paulo.

const TIME_ZONE = 'America/Sao_Paulo';

const currencyFormatter = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: TIME_ZONE,
});

/** "45.00" ou 45 → "R$ 45,00". A API envia valores decimais como texto. */
export function formatCurrency(value) {
  const number = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(number)) return '';
  // Intl usa espaço não separável depois de "R$"; o texto fica com espaço comum.
  return currencyFormatter.format(number).replace(/\u00a0/g, ' ');
}

/** Data ISO (timestamptz) → "dd/mm/aaaa" no fuso America/Sao_Paulo. */
export function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return dateFormatter.format(date);
}
