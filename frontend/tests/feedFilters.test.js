import { describe, expect, it } from 'vitest';
import { feedFiltersFromSearch, toFeedQuery } from '../src/utils/feedFilters';

describe('filtros do feed na URL (seção 11.2)', () => {
  it('lê só os filtros conhecidos, sem valores vazios e com listas ordenadas', () => {
    const search = new URLSearchParams(
      'q=%20furadeira%20&categories=3&categories=1&categories=3&tags=&sort=price_asc&page=2&price_min=',
    );

    expect(feedFiltersFromSearch(search)).toEqual({
      q: 'furadeira',
      sort: 'price_asc',
      categories: ['1', '3'],
    });
  });

  it('URL sem filtros vira objeto vazio', () => {
    expect(feedFiltersFromSearch(new URLSearchParams())).toEqual({});
  });

  it('monta a query da API com categories[] e tags[], limit e cursor (seção 10)', () => {
    const query = new URLSearchParams(
      toFeedQuery({ q: 'barraca', categories: ['1', '2'], tags: ['camping'] }, 'abc'),
    );

    expect(query.get('q')).toBe('barraca');
    expect(query.getAll('categories[]')).toEqual(['1', '2']);
    expect(query.getAll('tags[]')).toEqual(['camping']);
    expect(query.get('limit')).toBe('20');
    expect(query.get('cursor')).toBe('abc');
  });

  it('sem cursor, pede a primeira página', () => {
    expect(toFeedQuery({})).toBe('limit=20');
  });
});
