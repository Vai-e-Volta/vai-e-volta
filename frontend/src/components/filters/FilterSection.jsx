import { useId } from 'react';

const clearButtonClassName =
  'rounded text-sm text-flow hover:text-flow-hover focus-visible:outline-none ' +
  'focus-visible:ring-2 focus-visible:ring-flow';

/** Bloco da barra lateral com título e, quando há algo marcado, o botão "Limpar". */
export default function FilterSection({ title, onClear, children }) {
  const titleId = useId();
  return (
    <div
      role="group"
      aria-labelledby={titleId}
      className="border-b border-line pb-5 last:border-b-0"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id={titleId} className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </h2>
        {onClear && (
          <button
            type="button"
            onClick={onClear}
            aria-label={`Limpar ${title.toLowerCase()}`}
            className={clearButtonClassName}
          >
            Limpar
          </button>
        )}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}
