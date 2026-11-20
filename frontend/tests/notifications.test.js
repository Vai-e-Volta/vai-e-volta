import { describe, expect, it } from 'vitest';
import { describeNotification } from '../src/utils/notifications';

// Payloads fictícios, com os campos da seção 5.
const base = { rental_id: 'r1', listing_id: 7, listing_title: 'Barraca' };

describe('UT-NTF-01 texto e destino de cada aviso (seção 5, RN-67)', () => {
  it.each([
    [
      'proposal_received',
      { renter_username: 'davi_teste', start_date: '2026-12-01', end_date: '2026-12-03' },
      '@davi_teste propôs alugar “Barraca” de 01/12/2026 a 03/12/2026.',
      '/alugueis?visao=anuncios',
    ],
    [
      'proposal_accepted',
      { start_date: '2026-12-01', end_date: '2026-12-03' },
      'Sua proposta para “Barraca” foi aceita (01/12/2026 a 03/12/2026).',
      '/alugueis?visao=alugando',
    ],
    [
      'proposal_rejected',
      { reason: 'owner' },
      'O dono recusou sua proposta para “Barraca”.',
      '/alugueis?visao=alugando&aba=historico',
    ],
    [
      'proposal_rejected',
      { reason: 'overlap' },
      'Sua proposta para “Barraca” foi recusada: outra proposta foi aceita para essas datas.',
      '/alugueis?visao=alugando&aba=historico',
    ],
    [
      'proposal_rejected',
      { reason: 'listing_unavailable' },
      'Sua proposta para “Barraca” foi recusada: o anúncio foi pausado ou excluído.',
      '/alugueis?visao=alugando&aba=historico',
    ],
    [
      'proposal_expired',
      {},
      'Sua proposta para “Barraca” expirou sem resposta do dono.',
      '/alugueis?visao=alugando&aba=historico',
    ],
    [
      'rental_starting',
      { role: 'renter', start_date: '2026-12-01' },
      'Amanhã começa o seu aluguel de “Barraca”.',
      '/alugueis?visao=alugando',
    ],
    [
      'rental_starting',
      { role: 'owner', start_date: '2026-12-01' },
      'Amanhã “Barraca” sai para o locatário.',
      '/alugueis?visao=anuncios',
    ],
    [
      'return_due',
      { role: 'renter', end_date: '2026-12-03' },
      'Amanhã, 03/12/2026, é o último dia para devolver “Barraca”.',
      '/alugueis?visao=alugando',
    ],
    [
      'return_due',
      { role: 'owner', end_date: '2026-12-03' },
      '“Barraca” deve voltar amanhã, 03/12/2026.',
      '/alugueis?visao=anuncios',
    ],
    [
      'rental_overdue',
      { role: 'renter', end_date: '2026-12-03' },
      'A devolução de “Barraca” está atrasada: o prazo era 03/12/2026.',
      '/alugueis?visao=alugando',
    ],
    [
      'rental_overdue',
      { role: 'owner', end_date: '2026-12-03' },
      '“Barraca” deveria ter voltado em 03/12/2026. Combine a devolução com o locatário.',
      '/alugueis?visao=anuncios',
    ],
    [
      'return_requested',
      { renter_username: 'davi_teste' },
      '@davi_teste avisou que vai devolver “Barraca” antes do prazo.',
      '/alugueis?visao=anuncios',
    ],
    [
      'rental_completed',
      { returned_on: '2026-12-02', estimated_total: '30.00' },
      'O dono confirmou a devolução de “Barraca” em 02/12/2026. Valor estimado: R$ 30,00.',
      '/alugueis?visao=alugando&aba=historico',
    ],
    [
      'rental_canceled',
      { canceled_by: 'renter' },
      'O locatário cancelou o aluguel de “Barraca”.',
      '/alugueis?visao=anuncios&aba=historico',
    ],
    [
      'rental_canceled',
      { canceled_by: 'account_deleted', role: 'renter' },
      'O aluguel de “Barraca” foi cancelado porque a outra conta foi excluída.',
      '/alugueis?visao=alugando&aba=historico',
    ],
  ])('%s', (type, extra, text, to) => {
    expect(describeNotification({ type, payload: { ...base, ...extra } })).toEqual({ text, to });
  });

  it('tipo desconhecido ou payload vazio não quebra a tela', () => {
    expect(describeNotification({ type: 'novo_tipo', payload: base })).toEqual({
      text: 'Você tem um novo aviso.',
      to: '/alugueis',
    });
    expect(describeNotification({ type: 'proposal_expired', payload: null }).text).toBe(
      'Sua proposta para o item expirou sem resposta do dono.',
    );
  });
});
