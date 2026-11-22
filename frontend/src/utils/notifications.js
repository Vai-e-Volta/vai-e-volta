import { formatCurrency, isoToBrDate } from './format';

// Seção 5: o banco guarda só type e payload; o texto é montado aqui e o clique leva ao
// destino do tipo (RN-67). Visão e aba de /alugueis seguem os parâmetros da H019-4.
const OWNER = '/alugueis?visao=anuncios';
const RENTER = '/alugueis?visao=alugando';
const OWNER_HISTORY = `${OWNER}&aba=historico`;
const RENTER_HISTORY = `${RENTER}&aba=historico`;

const period = (p) => `${isoToBrDate(p.start_date)} a ${isoToBrDate(p.end_date)}`;
const byRole = (p) => (p.role === 'owner' ? OWNER : RENTER);

const BUILDERS = {
  proposal_received: (p, item) => ({
    text: `@${p.renter_username} propôs alugar ${item} de ${period(p)}.`,
    to: OWNER,
  }),
  proposal_accepted: (p, item) => ({
    text: `Sua proposta para ${item} foi aceita (${period(p)}).`,
    to: RENTER,
  }),
  proposal_rejected: (p, item) => {
    const why = {
      overlap: ': outra proposta foi aceita para essas datas',
      listing_unavailable: ': o anúncio foi pausado ou excluído',
    }[p.reason];
    return {
      text: why
        ? `Sua proposta para ${item} foi recusada${why}.`
        : `O dono recusou sua proposta para ${item}.`,
      to: RENTER_HISTORY,
    };
  },
  proposal_expired: (p, item) => ({
    text: `Sua proposta para ${item} expirou sem resposta do dono.`,
    to: RENTER_HISTORY,
  }),
  rental_starting: (p, item) => ({
    text:
      p.role === 'owner'
        ? `Amanhã ${item} sai para o locatário.`
        : `Amanhã começa o seu aluguel de ${item}.`,
    to: byRole(p),
  }),
  return_due: (p, item) => ({
    text:
      p.role === 'owner'
        ? `${item} deve voltar amanhã, ${isoToBrDate(p.end_date)}.`
        : `Amanhã, ${isoToBrDate(p.end_date)}, é o último dia para devolver ${item}.`,
    to: byRole(p),
  }),
  rental_overdue: (p, item) => ({
    text:
      p.role === 'owner'
        ? `${item} deveria ter voltado em ${isoToBrDate(p.end_date)}. Combine a devolução com o locatário.`
        : `A devolução de ${item} está atrasada: o prazo era ${isoToBrDate(p.end_date)}.`,
    to: byRole(p),
  }),
  return_requested: (p, item) => ({
    text: `@${p.renter_username} avisou que vai devolver ${item} antes do prazo.`,
    to: OWNER,
  }),
  rental_completed: (p, item) => ({
    text: `O dono confirmou a devolução de ${item} em ${isoToBrDate(p.returned_on)}. Valor estimado: ${formatCurrency(p.estimated_total)}.`,
    to: RENTER_HISTORY,
  }),
  rental_canceled: (p, item) =>
    p.canceled_by === 'account_deleted'
      ? {
          text: `O aluguel de ${item} foi cancelado porque a outra conta foi excluída.`,
          to: p.role === 'renter' ? RENTER_HISTORY : OWNER_HISTORY,
        }
      : { text: `O locatário cancelou o aluguel de ${item}.`, to: OWNER_HISTORY },
};

/** Texto e destino de um aviso (seção 5, RN-67). Tipo desconhecido leva a /alugueis. */
export function describeNotification({ type, payload }) {
  const data = payload ?? {};
  const item = data.listing_title ? `“${data.listing_title}”` : 'o item';
  const build = BUILDERS[type];
  const { text, to } = build
    ? build(data, item)
    : { text: 'Você tem um novo aviso.', to: '/alugueis' };
  return { text, to };
}
