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

const isoDateFormatter = new Intl.DateTimeFormat('en-CA', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  timeZone: TIME_ZONE,
});

const relativeFormatter = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' });

const RELATIVE_UNITS = [
  ['year', 365 * 24 * 60 * 60],
  ['month', 30 * 24 * 60 * 60],
  ['day', 24 * 60 * 60],
  ['hour', 60 * 60],
  ['minute', 60],
];

/** Tempo desde a publicação (F-23): "há 5 minutos", "ontem", "há 3 dias". */
export function formatRelativeTime(value, now = new Date()) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const seconds = Math.max(0, Math.round((now.getTime() - date.getTime()) / 1000));
  for (const [unit, size] of RELATIVE_UNITS) {
    if (seconds >= size) return relativeFormatter.format(-Math.floor(seconds / size), unit);
  }
  return 'agora mesmo';
}

/** Data de hoje em America/Sao_Paulo no formato AAAA-MM-DD (RN-69). */
export function todayIso(now = new Date()) {
  return isoDateFormatter.format(now);
}

/** Máscara dd/mm/aaaa enquanto a pessoa digita: "01122026" → "01/12/2026". */
export function maskDate(value) {
  const digits = String(value).replace(/\D/g, '').slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join('/');
}

/** "dd/mm/aaaa" → "AAAA-MM-DD" (formato da API); null se a data não existir. */
export function parseBrDate(value) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(String(value).trim());
  if (!match) return null;
  const [, day, month, year] = match;
  if (Number(year) < 1900) return null;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  if (date.getUTCDate() !== Number(day) || date.getUTCMonth() !== Number(month) - 1) return null;
  return `${year}-${month}-${day}`;
}

/** "AAAA-MM-DD" → "dd/mm/aaaa", para mostrar no campo. */
export function isoToBrDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '');
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '';
}
