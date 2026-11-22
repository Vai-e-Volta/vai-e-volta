import { useQuery } from '@tanstack/react-query';
import { getCategories } from '../../services/listings';
import FilterSection from './FilterSection';
import { checkboxClassName } from './filterStyles';

/** Categorias fixas em lista lateral (F-25); várias marcadas combinam com OU (RN-26). */
export default function CategoryFilter({ selected, onChange }) {
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
