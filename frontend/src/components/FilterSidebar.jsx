import { useQuery } from '@tanstack/react-query';
import { useId } from 'react';
import { getCategories } from '../services/listings';

const checkboxClassName =
  'h-4 w-4 shrink-0 rounded border-line bg-field accent-accent ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent';

const clearButtonClassName =
  'rounded text-sm text-flow hover:text-flow-hover focus-visible:outline-none ' +
  'focus-visible:ring-2 focus-visible:ring-flow';

/** Bloco da barra lateral com título e, quando há algo marcado, o botão "Limpar". */
function FilterSection({ title, onClear, children }) {
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

function CategoryFilter({ selected, onChange }) {
  const {
    data: categories,
    error,
    isPending,
  } = useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
    staleTime: Infinity,
  });

  function toggle(id) {
    const value = String(id);
    onChange(
      selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value],
    );
  }

  return (
    <FilterSection title="Categorias" onClear={selected.length > 0 ? () => onChange([]) : null}>
      {isPending && <p className="text-sm text-slate-400">Carregando…</p>}
      {error && <p className="text-sm text-red-300">{error.message}</p>}
      {categories && (
        <ul className="flex flex-col gap-1">
          {categories.map((category) => (
            <li key={category.id}>
              <label className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 text-slate-200 hover:bg-white/5">
                <input
                  type="checkbox"
                  checked={selected.includes(String(category.id))}
                  onChange={() => toggle(category.id)}
                  className={checkboxClassName}
                />
                {category.name}
              </label>
            </li>
          ))}
        </ul>
      )}
    </FilterSection>
  );
}

/**
 * Barra lateral de filtros do feed (seção 11.3). Por enquanto tem as categorias fixas
 * (F-25); marcar mais de uma traz itens de qualquer uma delas (RN-26).
 */
export default function FilterSidebar({ filters, onChange }) {
  return (
    <div className="flex flex-col gap-5">
      <CategoryFilter
        selected={filters.categories ?? []}
        onChange={(categories) => onChange({ categories })}
      />
    </div>
  );
}
