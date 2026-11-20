// Situação calculada pela API (RN-65), já em português. Pela regra do vai e volta, o item
// que saiu ou vai sair fica em pêssego e o que voltou fica em menta.
const STYLES = {
  Aguardando: 'border-slate-500/50 text-slate-200',
  Reservado: 'border-accent/50 text-accent',
  'Em andamento': 'border-accent bg-accent/15 text-accent',
  Atrasado: 'border-red-400/60 bg-red-400/10 text-red-300',
  Concluído: 'border-flow/50 bg-flow/10 text-flow',
};

const MUTED = 'border-line text-slate-400';

/** Selo da situação do aluguel (seção 11.3). */
export default function StatusBadge({ situation }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
        STYLES[situation] ?? MUTED
      }`}
    >
      {situation}
    </span>
  );
}
