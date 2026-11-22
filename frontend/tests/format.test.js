import { describe, expect, it } from 'vitest';
import {
  formatCurrency,
  formatDate,
  formatRelativeTime,
  isoToBrDate,
  maskDate,
  parseBrDate,
} from '../src/utils/format';

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

  it('formata o tempo desde a publicação (F-23)', () => {
    const now = new Date('2026-11-20T12:00:00Z');
    expect(formatRelativeTime('2026-11-20T11:59:30Z', now)).toBe('agora mesmo');
    expect(formatRelativeTime('2026-11-20T11:55:00Z', now)).toBe('há 5 minutos');
    expect(formatRelativeTime('2026-11-20T09:00:00Z', now)).toBe('há 3 horas');
    expect(formatRelativeTime('2026-11-19T10:00:00Z', now)).toBe('ontem');
    expect(formatRelativeTime('2026-11-18T10:00:00Z', now)).toBe('anteontem');
    expect(formatRelativeTime('2026-11-10T12:00:00Z', now)).toBe('há 10 dias');
    expect(formatRelativeTime('2026-08-20T12:00:00Z', now)).toBe('há 3 meses');
    expect(formatRelativeTime('2024-11-01T12:00:00Z', now)).toBe('há 2 anos');
    // Relógio da pessoa um pouco atrasado não gera "daqui a".
    expect(formatRelativeTime('2026-11-20T12:00:30Z', now)).toBe('agora mesmo');
    expect(formatRelativeTime('x', now)).toBe('');
  });

  it('datas dd/mm/aaaa na tela e AAAA-MM-DD na API (RN-69)', () => {
    expect(maskDate('01122026')).toBe('01/12/2026');
    expect(maskDate('0112')).toBe('01/12');
    expect(maskDate('01/12/20261')).toBe('01/12/2026');
    expect(parseBrDate('29/02/2028')).toBe('2028-02-29');
    expect(parseBrDate('29/02/2026')).toBeNull();
    expect(parseBrDate('1/12/2026')).toBeNull();
    expect(parseBrDate('01/01/0000')).toBeNull();
    expect(isoToBrDate('2026-12-01')).toBe('01/12/2026');
    expect(isoToBrDate('')).toBe('');
  });
});
