import FilterSection from './FilterSection';
import { checkboxClassName } from './filterStyles';

/** Filtro "Favoritos" (F-26): só os anúncios marcados com o coração. */
export default function FavoritesFilter({ checked, onChange }) {
  return (
    <FilterSection title="Favoritos">
      <label className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 text-slate-200 hover:bg-white/5">
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked ? 'true' : null)}
          className={checkboxClassName}
        />
        Só meus favoritos
      </label>
    </FilterSection>
  );
}
