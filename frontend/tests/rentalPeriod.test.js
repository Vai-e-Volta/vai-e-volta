import { describe, expect, it } from 'vitest';
import {
  estimatedTotal,
  proposalSummary,
  rentalDays,
  validateProposal,
} from '../src/utils/rentalPeriod';

const LISTING = {
  daily_price: '15.00',
  max_days: 5,
  available_from: '2026-12-01',
  available_until: '2026-12-31',
};
const TODAY = '2026-11-20';

describe('UT-RNT-01 duração inclusiva (RN-36)', () => {
  it('conta início e fim', () => {
    expect(rentalDays('2026-12-01', '2026-12-03')).toBe(3);
    expect(rentalDays('2026-12-01', '2026-12-01')).toBe(1);
    // Virada de mês e de ano.
    expect(rentalDays('2026-12-30', '2027-01-02')).toBe(4);
  });
});

describe('valor estimado (RN-43, F-33)', () => {
  it('multiplica o valor por dia pela duração', () => {
    expect(estimatedTotal('15.00', 3)).toBe('45.00');
    expect(estimatedTotal('12.50', 2)).toBe('25.00');
  });

  it('o resumo só aparece com um período válido', () => {
    expect(proposalSummary({ start: '01/12/2026', end: '03/12/2026' }, '15.00')).toEqual({
      days: 3,
      total: '45.00',
    });
    expect(proposalSummary({ start: '01/12/2026', end: '' }, '15.00')).toBeNull();
    expect(proposalSummary({ start: '03/12/2026', end: '01/12/2026' }, '15.00')).toBeNull();
  });
});

describe('validação do período na tela (RN-37 a RN-39)', () => {
  const check = (start, end) => validateProposal({ start, end }, LISTING, TODAY);

  it('aceita período válido e devolve as datas no formato da API', () => {
    expect(check('01/12/2026', '05/12/2026')).toEqual({
      values: { start_date: '2026-12-01', end_date: '2026-12-05' },
      errors: {},
    });
  });

  it('exige as duas datas válidas', () => {
    expect(check('', '').errors).toEqual({
      start_date: 'Informe a data de início.',
      end_date: 'Informe a data de fim.',
    });
    expect(check('32/12/2026', '01/12/2026').errors.start_date).toBe(
      'Data inválida. Use dd/mm/aaaa.',
    );
  });

  it('não aceita início no passado (RN-39) nem fim antes do início', () => {
    expect(check('19/11/2026', '20/11/2026').errors.start_date).toBe(
      'O início não pode ser antes de hoje.',
    );
    expect(check('05/12/2026', '01/12/2026').errors.end_date).toBe(
      'O fim deve ser no mesmo dia ou depois do início.',
    );
  });

  it('o período fica dentro da janela (RN-38)', () => {
    expect(check('28/12/2026', '02/01/2027').errors.end_date).toBe(
      'Escolha datas entre 01/12/2026 e 31/12/2026.',
    );
  });

  it('a duração não passa do prazo máximo (RN-37)', () => {
    expect(check('01/12/2026', '06/12/2026').errors.end_date).toBe(
      'Este item é alugado por no máximo 5 dias.',
    );
    expect(
      validateProposal(
        { start: '01/12/2026', end: '02/12/2026' },
        { ...LISTING, max_days: 1 },
        TODAY,
      ).errors.end_date,
    ).toBe('Este item é alugado por no máximo 1 dia.');
  });
});
