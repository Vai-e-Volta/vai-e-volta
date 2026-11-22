import { parseBrDate } from './format';
import { parsePrice } from './listingValidation';

// Filtros do feed (seção 11.2): ficam nos query params da URL para que recarregar ou
// compartilhar o link mantenha a busca. Os nomes seguem os parâmetros de
// GET /api/listings (seção 10); listas aparecem repetidas na URL da página
// (?categories=1&categories=2) e vão à API como categories[] e tags[].

/** Filtros de valor único, na ordem em que vão à API. */
const SINGLE_KEYS = [
  'q',
  'price_min',
  'price_max',
  'availability',
  'needed_from',
  'needed_until',
  'favorites',
  'sort',
];

/** Filtros de lista: nome na URL da página → nome na API. */
const LIST_KEYS = { categories: 'categories[]', tags: 'tags[]' };

export const FEED_PAGE_SIZE = 20;

/**
 * Lê os filtros da URL da página. Ignora parâmetros desconhecidos e valores vazios e
 * ordena as listas, para que a chave ['listings', filtros] não mude à toa.
 */
export function feedFiltersFromSearch(searchParams) {
  const filters = {};
  for (const key of SINGLE_KEYS) {
    const value = searchParams.get(key)?.trim();
    if (value) filters[key] = value;
  }
  for (const key of Object.keys(LIST_KEYS)) {
    const values = [
      ...new Set(
        searchParams
          .getAll(key)
          .map((value) => value.trim())
          .filter(Boolean),
      ),
    ].sort();
    if (values.length > 0) filters[key] = values;
  }
  return filters;
}

/** Monta a query string de GET /api/listings a partir dos filtros e do cursor. */
export function toFeedQuery(filters, cursor = null) {
  const params = new URLSearchParams();
  for (const key of SINGLE_KEYS) {
    if (filters[key]) params.set(key, filters[key]);
  }
  for (const [key, apiKey] of Object.entries(LIST_KEYS)) {
    for (const value of filters[key] ?? []) params.append(apiKey, value);
  }
  params.set('limit', String(FEED_PAGE_SIZE));
  if (cursor) params.set('cursor', cursor);
  return params.toString();
}

/**
 * Nova URLSearchParams com as mudanças aplicadas: texto vazio, null ou lista vazia
 * removem o filtro. As listas aparecem repetidas na URL (?categories=1&categories=2).
 */
export function applyFilterChanges(searchParams, changes) {
  const next = new URLSearchParams(searchParams);
  for (const [key, value] of Object.entries(changes)) {
    next.delete(key);
    if (Array.isArray(value)) {
      for (const item of value) next.append(key, item);
    } else if (value !== null && value !== undefined && String(value).trim() !== '') {
      next.set(key, String(value).trim());
    }
  }
  return next;
}

/** "25.00" da URL → "25,00" para mostrar no campo. */
export function priceToInput(value) {
  return value ? value.replace('.', ',') : '';
}

/**
 * Faixa de preço digitada (F-18). Os dois campos são opcionais; cada um aceita "25",
 * "25,5" ou "R$ 25,50". Devolve os valores no formato da API ("25.50") ou os erros.
 */
export function parsePriceRange(minText, maxText) {
  const errors = {};
  const values = { price_min: null, price_max: null };
  for (const [key, text] of [
    ['price_min', minText],
    ['price_max', maxText],
  ]) {
    if (!text.trim()) continue;
    const price = parsePrice(text);
    if (price === null) errors[key] = 'Use um valor como 25 ou 25,50.';
    else values[key] = price;
  }
  if (
    !errors.price_min &&
    !errors.price_max &&
    values.price_min &&
    values.price_max &&
    Number(values.price_min) > Number(values.price_max)
  ) {
    errors.price_max = 'O máximo não pode ser menor que o mínimo.';
  }
  return { values, errors };
}

/** Ordenação do feed (F-20). A primeira é a padrão e não aparece na URL. */
export const SORT_OPTIONS = [
  { value: 'newest', label: 'Mais recentes' },
  { value: 'oldest', label: 'Mais antigos' },
  { value: 'price_asc', label: 'Menor preço' },
  { value: 'price_desc', label: 'Maior preço' },
];

/** Disponibilidade (F-21, RN-28). A primeira é a padrão e não aparece na URL. */
export const AVAILABILITY_OPTIONS = [
  { value: 'all', label: 'Todos' },
  { value: 'available_now', label: 'Disponíveis agora' },
  { value: 'rented_now', label: 'Atualmente alugados' },
];

/**
 * Período desejado (F-22), digitado em dd/mm/aaaa. Só vale com as duas datas (RN-29) e
 * vai à API como AAAA-MM-DD.
 */
export function parsePeriod(fromText, untilText) {
  const from = fromText.trim();
  const until = untilText.trim();
  if (!from && !until) return { values: { needed_from: null, needed_until: null }, errors: {} };
  const errors = {};
  const values = { needed_from: parseBrDate(from), needed_until: parseBrDate(until) };
  if (!from) errors.needed_from = 'Informe a data de início.';
  else if (!values.needed_from) errors.needed_from = 'Data inválida. Use dd/mm/aaaa.';
  if (!until) errors.needed_until = 'Informe a data de fim.';
  else if (!values.needed_until) errors.needed_until = 'Data inválida. Use dd/mm/aaaa.';
  if (!errors.needed_from && !errors.needed_until && values.needed_until < values.needed_from) {
    errors.needed_until = 'O fim deve ser no mesmo dia ou depois do início.';
  }
  return { values, errors };
}
