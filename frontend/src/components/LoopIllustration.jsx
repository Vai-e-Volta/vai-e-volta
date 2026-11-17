const ITEMS = [
  { label: 'Furadeira', delay: '0s', start: '8%' },
  { label: 'Barraca', delay: '-4.5s', start: '30%' },
  { label: 'Projetor', delay: '-9s', start: '58%' },
  { label: 'Bicicleta', delay: '-13.5s', start: '80%' },
];

/**
 * Ilustração da tela de acesso: itens circulando num laço que vai e volta,
 * com um aluguel de exemplo no centro. Puramente decorativa.
 */
export default function LoopIllustration() {
  return (
    <div aria-hidden="true" className="relative mx-auto h-[320px] w-[420px]">
      <svg viewBox="0 0 420 320" fill="none" className="absolute inset-0 h-full w-full">
        <defs>
          <marker
            id="arrow-vai"
            viewBox="0 0 10 10"
            refX="5"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M1 1 9 5 1 9" stroke="var(--color-accent)" strokeWidth="1.8" />
          </marker>
          <marker
            id="arrow-volta"
            viewBox="0 0 10 10"
            refX="5"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M1 1 9 5 1 9" stroke="var(--color-flow)" strokeWidth="1.8" />
          </marker>
        </defs>
        <path
          d="M 20 160 C 20 0, 400 0, 400 160"
          stroke="var(--color-accent)"
          strokeWidth="1.5"
          strokeDasharray="2 7"
          strokeLinecap="round"
          markerEnd="url(#arrow-vai)"
        />
        <path
          d="M 400 160 C 400 320, 20 320, 20 160"
          stroke="var(--color-flow)"
          strokeWidth="1.5"
          strokeDasharray="2 7"
          strokeLinecap="round"
          markerEnd="url(#arrow-volta)"
        />
        <text
          x="210"
          y="26"
          textAnchor="middle"
          className="fill-accent text-[11px] font-semibold tracking-[0.3em] uppercase"
        >
          vai
        </text>
        <text
          x="210"
          y="306"
          textAnchor="middle"
          className="fill-flow text-[11px] font-semibold tracking-[0.3em] uppercase"
        >
          volta
        </text>
      </svg>

      {ITEMS.map((item) => (
        <span
          key={item.label}
          className="loop-chip absolute left-0 top-0 whitespace-nowrap rounded-full border border-line bg-canvas px-2.5 py-1 text-xs font-medium text-slate-200 shadow-lg shadow-black/30"
          style={{ animationDelay: item.delay, offsetDistance: item.start }}
        >
          {item.label}
        </span>
      ))}

      <div className="absolute left-1/2 top-1/2 w-64 -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line bg-surface p-4 shadow-2xl shadow-black/40">
        <div className="flex items-center justify-between text-[11px] font-medium uppercase tracking-wider">
          <span className="text-slate-400">Aluguel aceito</span>
          <span className="flex items-center gap-1.5 text-flow">
            <span className="h-1.5 w-1.5 rounded-full bg-flow" />
            em curso
          </span>
        </div>
        <p className="mt-2 font-semibold text-white">Furadeira de impacto</p>
        <p className="text-sm text-slate-400">Centro · Rio Grande/RS</p>
        <div className="mt-3 flex items-end justify-between border-t border-line pt-3 tabular-nums">
          <div>
            <p className="whitespace-nowrap text-sm text-slate-200">12/10 a 14/10/2026</p>
            <p className="whitespace-nowrap text-xs text-slate-400">3 dias · R$ 15,00/dia</p>
          </div>
          <p className="whitespace-nowrap font-semibold text-accent">R$ 45,00</p>
        </div>
      </div>
    </div>
  );
}
