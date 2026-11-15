/** Bloco de uma seção da tela de configurações, com título e descrição. */
export function SettingsCard({ title, description, tone = 'default', children }) {
  const border = tone === 'danger' ? 'border-red-400/30' : 'border-line';
  const headingId = `settings-${title.toLowerCase().replace(/\W+/g, '-')}`;
  return (
    <section
      aria-labelledby={headingId}
      className={`rounded-2xl border ${border} bg-surface p-5 shadow-lg shadow-black/10 sm:p-7`}
    >
      <h2 id={headingId} className="text-lg font-semibold tracking-tight text-white">
        {title}
      </h2>
      {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
      {children}
    </section>
  );
}

const MESSAGE_STYLES = {
  error: 'border-red-400/40 bg-red-400/10 text-red-200',
  success: 'border-flow/30 bg-flow/10 text-teal-100',
  info: 'border-line bg-panel text-slate-300',
};

/** Resumo do envio: erro em role="alert"; sucesso e aviso em role="status". */
export function FormMessage({ message }) {
  if (!message) return null;
  return (
    <div
      role={message.type === 'error' ? 'alert' : 'status'}
      className={`mt-5 rounded-lg border px-4 py-3 text-sm ${MESSAGE_STYLES[message.type]}`}
    >
      {message.text}
    </div>
  );
}

export const submitClassName =
  'rounded-lg bg-accent px-6 py-3 font-semibold text-ink shadow-lg shadow-accent/10 ' +
  'transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 ' +
  'focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface ' +
  'disabled:opacity-60';
