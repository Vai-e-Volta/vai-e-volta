// Classes compartilhadas pelos blocos da barra lateral de filtros.

export const checkboxClassName =
  'h-4 w-4 shrink-0 rounded border-line bg-field accent-accent ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent';

/** Cores do botão de alternar (tags, atalhos de preço): marcado em pêssego. */
export function chipClassName(pressed) {
  return (
    'border text-sm transition-colors focus-visible:outline-none ' +
    'focus-visible:ring-2 focus-visible:ring-accent ' +
    (pressed
      ? 'border-accent bg-accent/15 text-accent'
      : 'border-line text-slate-300 hover:border-slate-500 hover:text-white')
  );
}

export const smallInputClassName =
  'w-full rounded-lg border border-line bg-field px-3 py-2 text-sm text-white ' +
  'placeholder:text-slate-400 hover:border-slate-500 focus:border-accent focus:outline-none ' +
  'focus:ring-2 focus:ring-accent/30 aria-[invalid=true]:border-red-400';
