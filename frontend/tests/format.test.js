import { describe, expect, it } from 'vitest';
import { formatCurrency, formatDate } from '../src/utils/format';

describe('utils/format', () => {
  it('formata valores em R$ 0,00 a partir do decimal em texto da API', () => {
    expect(formatCurrency('45.00')).toBe('R$ 45,00');
    expect(formatCurrency(1234.5)).toBe('R$ 1.234,50');
    expect(formatCurrency(null)).toBe('');
    expect(formatCurrency('abc')).toBe('');
  });

  it('formata datas em dd/mm/aaaa no fuso America/Sao_Paulo (RN-69)', () => {
    expect(formatDate('2026-10-10T12:00:00Z')).toBe('10/10/2026');
    // 01h UTC ainda é o dia anterior em São Paulo.
    expect(formatDate('2026-10-11T01:00:00Z')).toBe('10/10/2026');
    expect(formatDate(null)).toBe('');
    expect(formatDate('não é data')).toBe('');
  });
});
