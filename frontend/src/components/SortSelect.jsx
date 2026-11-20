import { useId } from 'react';
import { SORT_OPTIONS } from '../utils/feedFilters';

/** Ordenação do feed (F-20); "Mais recentes" é a padrão. */
export default function SortSelect({ value, onChange }) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="whitespace-nowrap text-sm text-slate-400">
        Ordenar por
      </label>
      <select
        id={id}
        value={value || SORT_OPTIONS[0].value}
        onChange={(event) => {
          const next = event.target.value;
          onChange(next === SORT_OPTIONS[0].value ? null : next);
        }}
        className="rounded-lg border border-line bg-field px-3 py-2 text-sm text-white hover:border-slate-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
